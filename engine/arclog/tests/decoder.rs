//! The decoder reads the token stream of a program into a program of the
//! same content, with each token the language model emits in its mask and
//! each token the engine emits among the tokens it forces, refuses a token
//! outside the mask, and forks a decode that leaves its source as it was.
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
use arclog::resolver::{resolve, resolve_last, GraphNodeIndex, ResolvedProgram, SolverScope};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, token_stream_with_paths, Control, DecodeSettings, Emitter, Token, Vocabulary};
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
    let written = checked(arclog);
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
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

#[test]
fn a_det_by_a_proposer_with_set_and_one_marks_decodes_to_its_content() {
    same_content("(DET &arr_dim ScaleRatio (SET))\n(DET &other UnchangedColor (SET) (ONE))\n");
}

#[test]
fn an_or_after_a_conjunct_of_a_branch_decodes_to_its_content() {
    same_content(&format!("{BG}{FG}(RULE &nested (input *P *Col) (OR ((&bg (:C Col)) (OR ((&fg P)) ((&fg (:Col Col))))) ((&fg P))))\n"));
}

#[test]
fn a_choose_of_two_never_clauses_decodes_to_its_stream() {
    let pick = "(CHOOSE &pick (from (&fg *P *Col)) (never (&fg *P *Col) (&fg (:P *P2) Col) (!= P P2) (&bg (:C Col))) (never (&fg *P *Col) (&fg P (:Col *C2)) (!= Col C2)))\n";
    round_trip(&format!("{BG}{FG}{pick}"));
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

/// What a resolution gives at `at` and for the nodes of the last form
/// after the first `nodes`: the resolution, the signature and the lifting
/// at `at`; the content of the last form at `form` and its side; and, of
/// each of its nodes, the hash of its content, its reads, its side, its
/// Example columns, its forms and its depth.
fn resolution_of_last(resolved: &ResolvedProgram, form: &NodePath, at: &NodePath, nodes: usize) -> String {
    let each = |node: usize| {
        let index = GraphNodeIndex(node as u32);
        format!(
            "{:?} {:?} {:?} {:?} {:?} {:?} {:?}",
            resolved.node_content(index).map(|content| content.content_hash()),
            resolved.graph.reads[node],
            resolved.side(index),
            resolved.example_columns(index, None),
            resolved.forms_of(index),
            resolved.depth(index),
            resolved.column_names(index),
        )
    };
    let per_node: Vec<_> = (nodes..resolved.graph.nodes.len()).map(each).collect();
    format!(
        "{:?} {:?} {:?} {:?} {:?} {:?} {:?}",
        resolved.resolution(at),
        resolved.signature(at),
        resolved.reads_lifted(at),
        resolved.content(form).map(|content| content.content_hash()),
        resolved.form_side(form),
        resolved.nodes_of(form),
        per_node
    )
}

/// What `compare_retargets` counted.
#[derive(Default)]
struct Retargets {
    compared: usize,
    retargeted: usize,
    to_node: usize,
    from_node: usize,
    in_instance: usize,
    after_key_body: usize,
}

/// At each state of the decode of the stream of `arclog` where the next
/// token may open an atom, the resolution of the form in progress for one
/// candidate that opens an atom of a lib relation, a relation macro, a
/// proposer or a program's relation, retargeted to another's relation,
/// gives what `resolve_last` gives for that other's program.
fn compare_retargets(arclog: &str) -> Retargets {
    let registry = Registry::get();
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let written = checked(arclog);
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    let mut counts = Retargets::default();
    for (token, emitter) in &stream {
        if matches!(emitter, Emitter::Engine) {
            continue;
        }
        {
            let mut resolved: Option<ResolvedProgram> = None;
            for id in 0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens") {
                let candidate = vocabulary.token(id).expect("an id of the vocabulary");
                if !matches!(candidate, Token::Lib(_) | Token::Proposer(_) | Token::Relation(_)) {
                    continue;
                }
                let mut fork = decoder.fork();
                if fork.step(candidate.clone()).is_err() {
                    continue;
                }
                let Some((program, Some(open))) = fork.partial() else { continue };
                let (_, complete) = program.value().forms.split_last().expect("a partial form");
                let earlier = std::sync::Arc::new(resolve(&Node::new(Program { forms: complete.into() }), None, &SolverScope::default(), registry).value);
                let form = NodePath::top(complete.len() as u32);
                let at = form.join(&open);
                let Some(atom) = node_at(NodeRef::Program(program.value()), &at).and_then(NodeRef::atom) else { continue };
                if !atom.sites.is_empty() {
                    continue;
                }
                let expected = resolve_last(&earlier, &program, registry);
                let nodes = earlier.graph.nodes.len();
                match resolved.as_mut() {
                    Some(held) => {
                        counts.compared += 1;
                        let before_node = matches!(held.resolution(&at), Some(arclog::resolver::Resolution::Node(_)));
                        if held.retarget_atom(&program, &at, &atom.relation, registry) {
                            counts.retargeted += 1;
                            counts.from_node += usize::from(before_node);
                            counts.to_node += usize::from(matches!(held.resolution(&at), Some(arclog::resolver::Resolution::Node(_))));
                            let in_form = matches!(program.value().forms.last(), Some(Form::Instance(_)));
                            counts.in_instance += usize::from(in_form);
                            counts.after_key_body += usize::from(in_form && at.0.get(1..3) != Some(&[PathStep(0), PathStep(0)][..]));
                            assert_eq!(resolution_of_last(held, &form, &at, nodes), resolution_of_last(&expected, &form, &at, nodes), "{candidate:?} after {token:?}");
                        }
                    }
                    None => resolved = Some(expected),
                }
            }
        }
        decoder.step(token.clone()).expect("a token of the stream");
    }
    counts
}

#[test]
fn a_retargeted_resolution_is_what_resolve_last_gives() {
    let boxes = "(INIT &boxes BoundingBox (key ((&comps.component ^Id)) (cell (P) (&comps.component *P Id))))\n";
    let counts = compare_retargets(&format!("{BG}{FG}{COMPS}{AXIS}{PRIOR}{boxes}"));
    let Retargets { compared, retargeted, in_instance, after_key_body, to_node, .. } = counts;
    assert!(to_node > 0, "no retarget to a node, {retargeted} retargets of {compared} candidates");
    assert!(compared > 0 && retargeted > 0, "{retargeted} retargets of {compared} candidates");
    assert!(in_instance > 0, "no retarget inside the instance form, {retargeted} retargets of {compared} candidates");
    assert!(after_key_body > 0, "no retarget outside the key body of the instance form, {in_instance} inside it");
}

/// The same for the atoms of a clause, which read the relations of the
/// forms before it as well.
#[test]
fn a_retargeted_resolution_of_a_clause_is_what_resolve_last_gives() {
    let lists = "(RULE &lists (input *P *Col) (NOT (&fg P)) (IF ((&bg (:C Col))) ((= *K 0)) ((input P (:Col *D)) (= *K 0))) (ALL ((input (:P *Q) (:Col Col))) ((&fg (:P Q)))))\n";
    let det = "(DET &arr_dim ScaleRatio)\n";
    for program in [format!("{BG}{FG}{lists}"), format!("{BG}{FG}{AXIS}{PRIOR}"), format!("{BG}{FG}{det}(RULE &cell (input *P *Col) (&fg P) (&bg (:C Col)) (&arr_dim))\n")] {
        let counts = compare_retargets(&program);
        assert!(counts.to_node > 0 && counts.from_node > 0, "{} retargets to a node, {} from one, of {} candidates", counts.to_node, counts.from_node, counts.compared);
    }
}

/// Along a stream, a step after `admissible` gives the step and the program
/// that a step on a fork with no mask computed gives, and a second
/// `admissible` gives the first mask.
#[test]
fn a_step_after_the_mask_is_the_step_with_no_mask() {
    let registry = Registry::get();
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let boxes = "(INIT &boxes BoundingBox (key ((&comps.component ^Id)) (cell (P) (&comps.component *P Id))))\n";
    let written = checked(&format!("{BG}{FG}{COMPS}{AXIS}{PRIOR}{boxes}"));
    let stream = token_stream(&written, &vocabulary).expect("the program has a stream");
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    for (token, emitter) in &stream {
        if matches!(emitter, Emitter::Engine) {
            continue;
        }
        let mut bare = decoder.fork();
        let mask = decoder.admissible();
        assert_eq!(decoder.admissible(), mask);
        let expected = bare.step(token.clone());
        let stepped = decoder.step(token.clone());
        assert_eq!(format!("{stepped:?}"), format!("{expected:?}"), "{token:?}");
        assert_eq!(format!("{:?}", decoder.partial()), format!("{:?}", bare.partial()), "{token:?}");
        assert_eq!(decoder.program(), bare.program(), "{token:?}");
    }
}
