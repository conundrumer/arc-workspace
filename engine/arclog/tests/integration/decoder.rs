//! The decoder reads the token stream of a program into a program of the
//! same content, with each token the language model emits in its mask and
//! each token the engine emits among the tokens it forces, refuses a token
//! outside the mask, gives the tokens it forces after a token, with no step,
//! and forks a decode that leaves its source as it was.
//! Each prefix that the checks cut from a decoded form is the partial
//! program that the decode shows at the token of its stream that ends the
//! prefix's node.

use arclog::check::prefix::prefixes;
use arclog::check::{check_program, CheckCache, CheckId, CheckedProgram, SolverClauses};
use arclog::decode::{Decoder, Refusal};
use arclog::eval::instance::Constructions;
use arclog::eval::values::Caps;
use arclog::program::path::{node_at, NodePath, NodeRef, PathStep};
use arclog::program::{FactRelation, Form, Node, Program};
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::{resolve, SolverScope};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, token_stream_with_paths, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::Color;

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
    inputs_with_task(Task { train: Box::new([]), test: Box::new([]) })
}

fn inputs_with_task(task: Task) -> Inputs {
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    Inputs { task, session: TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS), constructions }
}

/// Identity evidence gives ScaleRatio the value 1 and UnchangedColor the
/// color 3, including a model of that color's SET/ONE pick.
fn proposer_inputs() -> Inputs {
    let row: Box<[_]> = [Color::from_digit(3).expect("a color")].into();
    let grid = Grid::from_rows(Box::new([row])).expect("a grid");
    inputs_with_task(Task {
        train: Box::new([TrainPair { input: grid.clone(), output: grid }]),
        test: Box::new([]),
    })
}

fn decoder(inputs: &Inputs) -> Decoder<'_> {
    Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, &DecodeSettings::default())
}

/// Steps `decoder` through `stream`: each token of the language model in
/// the mask, and each token of the engine the next of the tokens the step
/// before it forced. Gives, for each token, the partial program the decode
/// shows after the step of the language model's token that it is or that
/// forces it.
fn walk(decoder: &mut Decoder<'_>, stream: &[(Token, Emitter)]) -> Vec<Option<Node<Program>>> {
    let mut forced: Vec<Token> = Vec::new();
    let mut shown = Vec::new();
    let mut last = None;
    for (index, (token, emitter)) in stream.iter().enumerate() {
        match emitter {
            Emitter::Engine => {
                assert_eq!(Some(token), (!forced.is_empty()).then(|| forced.remove(0)).as_ref(), "the engine's token at {index}");
                shown.push(last.clone());
            }
            Emitter::Model => {
                assert!(forced.is_empty(), "the engine forces {forced:?} before the token at {index}");
                let id = decoder.vocabulary().id(token).expect("a token of the vocabulary");
                assert!(decoder.admissible().contains(id), "the mask admits {token:?} at {index}");
                forced = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?} at {index}: {refusal:?}")).forced.into();
                last = decoder.partial().map(|(program, _)| program);
                shown.push(last.clone());
            }
        }
    }
    assert!(forced.is_empty(), "the engine forces {forced:?} after the stream");
    shown
}

/// The path in `form` of the node at `end` in the partial form `partial`
/// of a prefix: `end`, but at an input whose body the prefix ends in, where
/// the partial input holds no head site and the body stands first.
fn source_path(form: &Form, partial: &Form, end: &NodePath) -> NodePath {
    let mut steps = Vec::new();
    for (depth, step) in end.0.iter().enumerate() {
        let above = NodePath(end.0[..depth].into());
        match (node_at(NodeRef::from(form), &NodePath(steps.clone().into())), node_at(NodeRef::from(partial), &above)) {
            (Some(NodeRef::InstanceInput(input)), Some(NodeRef::InstanceInput(open))) if open.head.is_empty() && step.0 == 0 => steps.push(PathStep(input.head.len() as u32)),
            _ => steps.push(*step),
        }
    }
    NodePath(steps.into())
}

/// Asserts that each prefix of each form of `decoded`, after the forms
/// before it, is the program of `shown` at the last token of `paths` at or
/// below the path of the prefix's node, or, for a node that writes no
/// token, at the token that ends the prefix before it.
fn shows_each_prefix(decoded: &Node<Program>, paths: &[NodePath], shown: &[Option<Node<Program>>]) {
    let forms = &decoded.value().forms;
    let mut end = 0;
    for (index, form) in forms.iter().enumerate() {
        for prefix in prefixes(form) {
            let node = NodePath::top(index as u32).join(&source_path(form, &prefix.partial, &prefix.end));
            if let Some(last) = paths.iter().rposition(|path| path.0.starts_with(&node.0)) {
                end = last;
            }
            let program = Node::new(Program { forms: forms[..index].iter().cloned().chain([prefix.partial.clone()]).collect() });
            assert!(shown[end].as_ref() == Some(&program), "the decode shows {:?} at token {end}, and the prefix of form {index} at {:?} is {:?}", shown[end], prefix.end, prefix.partial);
        }
    }
}

/// The program written in `arclog`, checked, and the program that the
/// decode of its stream gives, checked, which gives the same stream.
fn round_trip(arclog: &str) -> (CheckedProgram, CheckedProgram) {
    round_trip_with_inputs(arclog, &inputs())
}

fn round_trip_with_inputs(arclog: &str, inputs: &Inputs) -> (CheckedProgram, CheckedProgram) {
    let written = checked(arclog);
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let mut decoder = decoder(inputs);
    let shown = walk(&mut decoder, &stream);
    let decoded = checked_decoded(decoder.program());
    let paths: Vec<NodePath> = token_stream_with_paths(&decoded, &vocabulary).expect("the decoded program has a stream").into_iter().map(|(_, _, path)| path).collect();
    shows_each_prefix(decoder.program(), &paths, &shown);
    assert_eq!(token_stream(&decoded, &vocabulary).expect("the decoded program has a stream"), stream);
    (written, decoded)
}

/// Asserts that the decode of the stream of `arclog` gives a program of
/// the content of the program written.
fn same_content(arclog: &str) {
    same_content_with_inputs(arclog, &inputs());
}

fn same_content_with_inputs(arclog: &str, inputs: &Inputs) {
    let (written, decoded) = round_trip_with_inputs(arclog, inputs);
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
    let lists = "(RULE &lists (input *P *Col) (NOT (&fg P)) (IF ((&bg (:C Col))) ((= *K 0)) ((input P (:Col *D)) (&axis_len (:N K)))) (ALL ((input (:P *Q) (:Col Col))) ((&fg (:P Q)))))\n";
    same_content(&format!("{BG}{FG}{AXIS}{lists}"));
}

#[test]
fn a_det_by_a_proposer_and_a_one_mark_decode_to_their_content() {
    same_content_with_inputs("(DET &arr_dim ScaleRatio)\n(RULE &cell (input *P *Col) (ONE P))\n", &proposer_inputs());
}

#[test]
fn a_det_by_a_proposer_with_set_and_one_marks_decodes_to_its_content() {
    same_content_with_inputs("(DET &arr_dim ScaleRatio (SET))\n(DET &other UnchangedColor (SET) (ONE))\n", &proposer_inputs());
}

#[test]
fn an_or_after_a_conjunct_of_a_branch_decodes_to_its_content() {
    same_content(&format!("{BG}{FG}(RULE &nested (input *P *Col) (OR ((&bg (:C Col)) (OR ((&fg P)) ((&fg (:Col Col))))) ((&fg P))))\n"));
}

/// The names of a key's columns are a part of the content of its instance,
/// and a decoded program names them by slot, so the decode of a keyed
/// instance gives its stream again and not its content.
#[test]
fn a_keyed_instance_decodes_to_its_stream() {
    let boxes = "(INIT &boxes BoundingBox (key ((&comps.component ^Id)) (cell (P) (&comps.component *P Id))))\n";
    round_trip(&format!("{BG}{FG}{COMPS}{boxes}"));
}

/// An input that reads its instance's own output reads a relation that the
/// stream has declared, so the decode steps the stream.
#[test]
fn an_instance_whose_input_reads_its_own_output_decodes_to_its_stream() {
    let walk = "(INIT &walk Unfold (start ((:t B)) (&bg (:C *B))) (initial_taken ((:item B)) (&bg (:C *B))) (initial_untaken ((:item B)) (&bg (:C *B))) (step ((:t B) (:t2 X)) (&bg (:C *B)) (&bg (:C *X)) (&walk.take (:t B) (:item X))))\n";
    round_trip(&format!("{BG}{walk}"));
}

/// Asserts that the query at `index` of the program written in `arclog`
/// has the content of the query at `index` of the decode of its stream.
fn same_query_content(arclog: &str, index: usize) {
    let inputs = inputs();
    let decoder = decoded(&inputs, arclog);
    assert_eq!(decoder.query_content(index), checked(arclog).program.query_content(index, Registry::get()));
}

/// A read of an instance's own output, at a site on a column of a type
/// parameter that the instance binds to one label, names that label by its
/// written name in a file and by a slot in a decode. The column is the
/// site's own column, so the query has one content in its file and in its
/// decode.
#[test]
fn an_instance_that_reads_its_own_output_on_a_column_of_one_label_has_the_query_content_of_its_file() {
    let walk = "(INIT &walk Unfold (start ((:t B)) (&bg (:C *B))) (initial_taken ((:item B2)) (&bg (:C *B2))) (initial_untaken ((:item B3)) (&bg (:C *B3))) (step ((:t B4) (:t2 X)) (&bg (:C *B4)) (&bg (:C *X)) (&walk.take (:t B4) (:item X))))\n";
    same_query_content(&format!("{BG}{walk}"), 1);
}

/// A read of an instance's own output, at a site on a field of the record
/// of a type parameter, names the field by its written name in a file and
/// by a slot in a decode. The field stands by its place in the record, so
/// the query has one content in its file and in its decode.
#[test]
fn an_instance_that_reads_a_field_of_its_own_output_has_the_query_content_of_its_file() {
    let walk = "(INIT &walk Unfold (start ((:t P Col)) (&fg *P *Col)) (initial_taken ((:item B)) (&bg (:C *B))) (initial_untaken ((:item B2)) (&bg (:C *B2))) (step ((:t (:P P2) (:Col Col2)) (:t2 (:P P3) (:Col Col3))) (&fg (:P *P2) (:Col *Col2)) (&fg (:P *P3) (:Col *Col3)) (&walk.take (:t (:P P2) (:Col Col2)))))\n";
    same_query_content(&format!("{BG}{FG}{walk}"), 2);
}

/// A read of a keyed instance's own output, at a site on a field of its
/// `key` record, names the field by the key's written label in a file and
/// by a slot in a decode. The field stands by the rank of its label in the
/// key's body, so the query has one content in its file and in its decode.
#[test]
fn a_keyed_instance_that_reads_a_key_field_of_its_own_output_has_the_query_content_of_its_file() {
    let key = "(&fg (:P Kp) (:Col Kc))";
    let walk = format!("(INIT &walk Unfold (key ((&fg (:P ^Kp) (:Col ^Kc))) (start ((:t B)) (&bg (:C *B)) {key}) (initial_taken ((:item B2)) (&bg (:C *B2)) {key}) (initial_untaken ((:item B3)) (&bg (:C *B3)) {key}) (step ((:t B4) (:t2 X)) (&bg (:C *B4)) (&bg (:C *X)) (&walk.take (:key Kp Kc) (:t B4) (:item X)))))\n");
    same_query_content(&format!("{BG}{FG}{walk}"), 2);
}

/// Each input of an instance is a body of its own, so a label of one name
/// in two inputs is two labels, and a head site of one label on a column
/// of a type parameter projects its own label. A file names that label by
/// its written name and a decode by a slot, so the query has one content in
/// its file and in its decode only where the name enters no head site.
#[test]
fn an_instance_whose_inputs_make_labels_of_one_name_has_the_query_content_of_its_file() {
    let walk = "(INIT &walk Unfold (start ((:t B)) (&bg (:C *B))) (initial_taken ((:item B)) (&bg (:C *B))) (initial_untaken ((:item B)) (&bg (:C *B))) (step ((:t B) (:t2 X)) (&bg (:C *B)) (&bg (:C *X))))\n";
    same_query_content(&format!("{BG}{walk}"), 1);
}

/// In a keyed instance, an input that reads its instance's own output and
/// a key label stands in the key clause, and the inputs that read neither
/// stand after it. The input that reads the output then precedes the
/// projections that bind the parameters it reads, so its body reads them
/// before the stream binds them, and the decode steps the stream.
#[test]
fn a_keyed_instance_whose_input_reads_its_own_output_before_its_parameters_bind_decodes_to_its_stream() {
    let walk = "(INIT &walk Unfold (key ((&fg (:P ^Kp) (:Col ^Kc))) (step ((:t B4) (:t2 X)) (&bg (:C *B4)) (&bg (:C *X)) (&fg (:P Kp) (:Col Kc)) (&walk.take (:t B4) (:item X)))) (start ((:t B)) (&bg (:C *B))) (initial_taken ((:item B2)) (&bg (:C *B2))) (initial_untaken ((:item B3)) (&bg (:C *B3))))\n";
    round_trip(&format!("{BG}{FG}{walk}"));
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

/// The mask at a state where the next token may open an atom admits the
/// tokens that a step of a fork admits, which runs every check on its one
/// token.
#[test]
fn the_mask_where_an_atom_opens_is_what_each_step_admits() {
    let inputs = inputs();
    let decoder = decoded(&inputs, BG);
    let prefixes: [&[Token]; 2] = [
        &[Token::Control(Control::Rule)],
        &[Token::Control(Control::Rule), Token::Relation(0), Token::Column(0), Token::Control(Control::Fresh)],
    ];
    for prefix in prefixes {
        let mut at = decoder.fork();
        for token in prefix {
            at.step(token.clone()).expect("a clause that reads `&bg`");
        }
        let mask = at.admissible();
        let vocabulary = at.vocabulary();
        let mut admitted = 0;
        for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
            let token = vocabulary.token(id).expect("an id of the vocabulary");
            let stepped = at.fork().step(token.clone()).is_ok();
            assert_eq!(mask.contains(id), stepped, "{token:?} after {prefix:?}");
            admitted += usize::from(stepped);
        }
        assert!(admitted > 1, "the mask admits several tokens after {prefix:?}");
    }
}

/// Along a stream, at each state, `admits` of any ids gives the verdicts that
/// `forced` gives for those tokens, whether the decode holds the mask of its
/// state or not, and leaves the decode's program and trace as they were.
#[test]
fn admits_is_the_verdict_of_forced_for_each_token() {
    let registry = Registry::get();
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let boxes = "(INIT &boxes BoundingBox (key ((&comps.component ^Id)) (cell (P) (&comps.component *P Id))))\n";
    let written = checked(&format!("{BG}{FG}{COMPS}{AXIS}{PRIOR}{boxes}"));
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    let ids: Vec<u32> = (0..vocabulary.len() as u32).collect();
    let (mut admitted, mut refused) = (0, 0);
    for (token, emitter) in &stream {
        if matches!(emitter, Emitter::Engine) {
            continue;
        }
        let expected: Vec<bool> = ids.iter().map(|&id| decoder.forced(vocabulary.token(id).expect("an id of the vocabulary")).is_ok()).collect();
        let trace = decoder.trace().len();
        let program = decoder.program().clone();
        let few: Vec<u32> = ids.iter().copied().step_by(7).collect();
        assert_eq!(decoder.admits(&few), few.iter().map(|&id| expected[id as usize]).collect::<Vec<_>>(), "{token:?}, a subset");
        assert_eq!(decoder.admits(&ids), expected, "{token:?}, every token");
        assert_eq!(decoder.trace().len(), trace, "{token:?}");
        assert_eq!(&program, decoder.program(), "{token:?}");
        decoder.admissible();
        assert_eq!(decoder.admits(&ids), expected, "{token:?}, mask held");
        admitted += expected.iter().filter(|&&verdict| verdict).count();
        refused += expected.iter().filter(|&&verdict| !verdict).count();
        decoder.step(token.clone()).expect("a token of the stream");
    }
    assert!(admitted > 0 && refused > 0, "{admitted} admitted, {refused} refused");
}

/// At a state where `END` ends a `RULE` clause, `forced` of a token gives
/// the tokens that the step of the token on a fork gives as forced, whether
/// the decode holds the mask of its state or not, leaves the decode's trace
/// and program as they were, and refuses a token outside the mask as the
/// step does.
#[test]
fn forced_is_the_forced_of_the_step_and_leaves_the_decode_as_it_was() {
    let inputs = inputs();
    let mut at = decoded(&inputs, BG);
    for token in [Token::Control(Control::Rule), Token::Relation(0), Token::Column(0), Token::Control(Control::Fresh)] {
        at.step(token).expect("a clause that reads `&bg`");
    }
    let closer = Token::Control(Control::End);
    let outside = Token::Control(Control::Rule);
    let expected = at.fork().step(closer.clone()).expect("the closer is in the mask").forced.to_vec();
    let refused = at.fork().step(outside.clone()).expect_err("a `RULE` inside a clause is outside the mask");
    let trace = at.trace().len();
    let program = at.program().clone();
    for held in [false, true] {
        if held {
            let id = at.vocabulary().id(&closer).expect("a token of the vocabulary");
            assert!(at.admissible().contains(id));
        }
        assert_eq!(at.forced(&closer), Ok(expected.clone()), "mask held: {held}");
        assert_eq!(at.forced(&outside), Err(refused.clone()), "mask held: {held}");
        assert_eq!(at.trace().len(), trace, "mask held: {held}");
        assert_eq!(&program, at.program(), "mask held: {held}");
    }
}

/// Source-only regression fixtures for the static-pruning grammar boundary.
/// These use the native stream and checker; they perform no task evaluation.
fn static_refusal(arclog: &str) -> Option<Token> {
    let settings = DecodeSettings::default();
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let stream = token_stream(&checked(arclog), &vocabulary).expect("checked fixture stream");
    let inputs = inputs();
    let mut decoder = Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, &settings);
    for (token, emitter) in stream {
        if emitter == Emitter::Engine { continue; }
        match decoder.step_untested(token.clone()) {
            Ok(_) => {},
            Err(Refusal::Grammar(reason)) if reason.starts_with("static prune:") => return Some(token),
            Err(error) => panic!("unexpected refusal of {token:?}: {error:?}"),
        }
    }
    None
}

#[test]
fn static_prune_review_atom_closed_by_next_relation() {
    assert_eq!(static_refusal("(RULE &x (input *P) (inside (:A P) (:B P)) (input P (:Col *C)))"),
        Some(Token::Fact(FactRelation::Input)));
}

#[test]
fn static_prune_review_atom_closed_by_clause_end() {
    assert_eq!(static_refusal("(RULE &x (input *P) (inside (:A P) (:B P)))"),
        Some(Token::Control(Control::End)));
}

#[test]
fn static_prune_review_unadmitted_zero_equality_keeps_atom() {
    assert_eq!(static_refusal("(RULE &x (uniform_inset (:K 0) (:B *B)))"), None);
}

#[test]
fn static_prune_review_changed_interface_keeps_alias_atom() {
    // A literal zero does not satisfy compose's Offset-labelled type-rule
    // premise. Its output is Box, whereas equality to input.P is Position.
    assert_eq!(static_refusal("(RULE &x (input *P) (compose (:A P) (:B 0) (:C *Q)))"), None);
}
