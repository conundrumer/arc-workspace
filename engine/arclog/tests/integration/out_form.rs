//! The `OUT` form (`docs/arclog/arclog.md#the-out-form`): the checker refuses
//! each form that breaks a rule of it, whole and by prefix; a solver holds
//! one, in its tail; the decoder admits, inside one, only the tokens after
//! which some completion passes, and ends at the first that solves the train
//! pairs; the token stream writes it last; and the rule tests of a decode are
//! an observation that changes no mask.

use std::sync::Arc;

use arclog::check::lint::lint;
use arclog::check::prefix::{check_prefix, prefixes};
use arclog::check::{check_program, CheckCache, CheckId, PrefixResult, SolverClauses};
use arclog::decode::{Consistency, Decoder};
use arclog::diagnostic::{DiagnosticKind, Location};
use arclog::eval::instance::Constructions;
use arclog::eval::Caps;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::program::path::{NodePath, PathStep};
use arclog::program::{FactRelation, Node, Program};
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::{resolve, resolve_cases};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::Color;

/// The relation `&r` copies the input, and `&bar` and `&paint` give a cell's
/// position and a color alone.
const RELATIONS: &str = "(RULE &r (input *P *Col))\n(RULE &pos (input *P))\n(RULE &colr (input (:Col *Col)))\n";

fn path(steps: &[u32]) -> NodePath {
    NodePath(steps.iter().map(|step| PathStep(*step)).collect())
}

/// The lines of the errors of the check `Out` that the lint finds in `arclog`.
fn refused_lines(arclog: &str) -> Vec<u32> {
    let solver = read_solver("out", arclog, "", &|_| None).expect("the file reads").value;
    let mut lines: Vec<u32> = lint(&solver, Registry::get())
        .into_iter()
        .filter(|diagnostic| diagnostic.kind == DiagnosticKind::Check(CheckId::Out))
        .flat_map(|diagnostic| match diagnostic.location {
            Location::Places(places) => places.iter().map(|at| at.place.line).collect::<Vec<_>>(),
            Location::Path(_) => panic!("the lint gives each error at its places"),
        })
        .collect();
    lines.sort();
    lines.dedup();
    lines
}

/// The end of the first prefix of the last form of `arclog` that the check
/// `Out` refuses.
fn first_refused(arclog: &str) -> Option<NodePath> {
    let solver = read_solver("prefix", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let scope = solver.derived_relations();
    let forms = cases.concept().resolved.value.program.value().forms.clone();
    let (last, complete) = forms.split_last().expect("the file holds a form");
    for prefix in prefixes(last) {
        let held: Vec<_> = complete.iter().cloned().chain([prefix.partial.clone()]).collect();
        let program = resolve(&Node::new(Program { forms: held.into() }), None, &scope, registry).value;
        for (id, result) in check_prefix(&program, &clauses, registry, prefix.open().as_ref()) {
            if let (CheckId::Out, PrefixResult::Refuse(_)) = (id, result) {
                return Some(prefix.end);
            }
        }
    }
    None
}

/// The `OUT` forms that pass: the checker accepts them whole and by prefix.
#[test]
fn an_out_of_one_atom_with_two_sites_and_one_of_two_atoms_with_one_site_each_pass() {
    for out in ["(OUT (&r ^P ^Col))", "(OUT (&pos ^P) (&colr ^Col))", "(OUT (input ^P ^Col))", "(OUT (&r ^P) (input ^Col))"] {
        let program = format!("{RELATIONS}{out}\n");
        assert_eq!(refused_lines(&program), Vec::<u32>::new(), "{out}");
        assert_eq!(first_refused(&program), None, "{out}");
    }
}

/// An `OUT` form that breaks a rule of item 1 is refused whole, at its line,
/// and by prefix, at the first prefix no completion passes.
#[test]
fn an_out_that_breaks_a_rule_of_its_form_is_refused_whole_and_by_prefix() {
    let refused = [
        // one site, or none
        ("(OUT (&r ^P))", "a one-atom OUT holds two sites"),
        ("(OUT)", "an OUT holds an atom"),
        // three sites; a third atom
        ("(OUT (&r ^P ^Col ^P))", "three sites"),
        ("(OUT (&pos ^P) (&colr ^Col) (&r ^P))", "a third atom"),
        // two sites, then a second atom
        ("(OUT (&r ^P ^Col) (&colr ^Col))", "a second atom after two sites"),
        // a conjunct that is no atom
        ("(OUT (&r ^P ^Col) (!= P Col))", "a constraint"),
        ("(OUT (NOT (&r ^P ^Col)))", "a negated atom"),
        // a relation that is no `input` and no declared relation
        ("(OUT (dir_elem ^D ^D))", "a lib relation"),
        ("(OUT (ex_output ^E ^P))", "ex_output"),
        // a site that is not one label marked `^`
        ("(OUT (&r *P ^Col))", "a fresh label"),
        ("(OUT (&r P ^Col))", "a join"),
        ("(OUT (&r (:P 0) ^Col))", "zero"),
        // the types: a Position, then a Color
        ("(OUT (&r ^Col ^P))", "a Color first"),
        ("(OUT (&r ^P ^P2))", "a Position second"),
    ];
    for (out, why) in refused {
        let program = format!("{RELATIONS}{out}\n");
        assert!(!refused_lines(&program).is_empty() || first_refused(&program).is_some(), "{why}: {out}");
    }
}

#[test]
fn an_out_site_of_the_wrong_type_is_refused_where_its_label_stands() {
    // The label of a Color column first: refused where the label stands.
    let program = format!("{RELATIONS}(OUT (&colr ^Col))\n");
    assert_eq!(first_refused(&program), Some(path(&[0, 0, 0, 0])));
    let program = format!("{RELATIONS}(OUT (&r ^Col ^P))\n");
    assert_eq!(first_refused(&program), Some(path(&[0, 0, 0, 0])));
    // A second atom of a relation with no Color column.
    let program = format!("{RELATIONS}(OUT (&pos ^P) (&pos ^P))\n");
    assert!(first_refused(&program).is_some());
}

/// The file rules of item 4.
#[test]
fn a_block_holds_one_out_in_its_place_under_no_claim() {
    let one = format!("{RELATIONS}(OUT (&r ^P ^Col))\n");
    assert_eq!(refused_lines(&one), Vec::<u32>::new());
    let none = RELATIONS.to_owned();
    assert_eq!(refused_lines(&none), vec![3], "a solver with no `OUT`");
    let two = format!("{RELATIONS}(OUT (&r ^P ^Col))\n(OUT (input ^P ^Col))\n");
    assert_eq!(refused_lines(&two), vec![4, 5], "a solver with two");
    let equal = format!("{RELATIONS}(OUT (&r ^P ^Col))\n(OUT (&r ^P ^Col))\n");
    assert!(!refused_lines(&equal).is_empty(), "a solver with two equal forms");
    let before = format!("{RELATIONS}(OUT (&r ^P ^Col))\n(RULE &late (input *P))\n");
    assert_eq!(refused_lines(&before), vec![4], "an `OUT` before another form");
    let claim = "(INPUT cells \"the cells\"\n  (RULE &r (input *P *Col))\n  (OUT (&r ^P ^Col)))\n";
    assert!(!refused_lines(claim).is_empty(), "an `OUT` in a claim");
    let alt = format!("{RELATIONS}(ALTS $a \"which\" $Plain\n  (ALT $Own\n    (OUT (&r ^P ^Col))))\n(OUT (&r ^P ^Col))\n");
    assert_eq!(refused_lines(&alt), Vec::<u32>::new(), "an `OUT` in an `ALT` block");
    let alt_before = format!("{RELATIONS}(ALTS $a \"which\" $Plain\n  (ALT $Own\n    (OUT (&r ^P ^Col))\n    (RULE &late (input *P))))\n(OUT (&r ^P ^Col))\n");
    assert!(!refused_lines(&alt_before).is_empty(), "an `OUT` before another form of its `ALT` block");
    let alt_two = format!("{RELATIONS}(ALTS $a \"which\" $Plain\n  (ALT $Own\n    (OUT (&r ^P ^Col))\n    (OUT (input ^P ^Col))))\n(OUT (&r ^P ^Col))\n");
    assert!(!refused_lines(&alt_two).is_empty(), "two `OUT` forms in one `ALT` block");
}

/// The checked program of the arclog text `arclog`, with no solver files.
fn checked(arclog: &str) -> arclog::check::CheckedProgram {
    let solver = read_solver("decode", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

/// A task of one train pair, the input `1 2` and the output `output`.
struct Inputs {
    task: Task,
    judged: JudgedTask,
    session: TaskSession,
    constructions: Constructions,
}

fn inputs(input: &[u8], output: &[u8]) -> Inputs {
    let task = Task { train: Box::new([TrainPair { input: grid(input), output: grid(output) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    Inputs { task, judged, session: TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS), constructions }
}

fn decoder<'a>(inputs: &'a Inputs, settings: &'a DecodeSettings) -> Decoder<'a> {
    let train: Arc<[PairCandidates<'_>]> = inputs.judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    Decoder::new(&inputs.task, &inputs.session, Registry::get(), &inputs.constructions, settings).judging(train)
}

/// The tokens of the language model in the stream of `arclog`.
fn model_tokens(arclog: &str) -> Vec<Token> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&checked(arclog), &vocabulary).expect("the program has a stream");
    stream.into_iter().filter(|(_, emitter)| *emitter == Emitter::Model).map(|(token, _)| token).collect()
}

/// Steps `decoder` through `tokens`, and gives the consistency and the rule
/// test of each step that gave one.
fn walk(decoder: &mut Decoder<'_>, tokens: &[Token]) -> (Vec<Consistency>, Vec<Consistency>) {
    let (mut ends, mut rules) = (Vec::new(), Vec::new());
    for token in tokens {
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
        ends.extend(step.consistency);
        rules.extend(step.rule_test);
    }
    (ends, rules)
}

#[test]
fn a_one_atom_out_and_a_two_atom_out_solve_the_pairs_and_end_the_decode() {
    for (out, input) in [("(OUT (&r ^P ^Col))", [1, 2]), ("(OUT (&pos ^P) (&colr ^Col))", [1, 1])] {
        let inputs = inputs(&input, &input);
        let settings = DecodeSettings::default();
        let mut decoder = decoder(&inputs, &settings);
        let (ends, _) = walk(&mut decoder, &model_tokens(&format!("{RELATIONS}{out}\n")));
        assert!(matches!(&ends[..], [Consistency::Consistent { .. }]), "{out}: {ends:?}");
        assert_eq!(decoder.output(), Some(&path(&[3])), "{out}");
    }
}

/// A two-atom `OUT` reads the product of the projections: a relation of two
/// colors gives no grid.
#[test]
fn a_two_atom_out_whose_second_relation_holds_two_colors_gives_no_grid() {
    let inputs = inputs(&[1, 2], &[1, 1]);
    let settings = DecodeSettings::default();
    let mut decoder = decoder(&inputs, &settings);
    let (ends, _) = walk(&mut decoder, &model_tokens(&format!("{RELATIONS}(OUT (&pos ^P) (&colr ^Col))\n")));
    assert!(matches!(&ends[..], [Consistency::NotConsistent]), "{ends:?}");
}

/// A decode goes on after an `OUT` that does not hold, and ends at the first
/// that does.
#[test]
fn a_decode_goes_on_after_an_out_that_does_not_hold_and_ends_at_the_one_that_does() {
    let inputs = inputs(&[1, 2], &[3, 3]);
    let settings = DecodeSettings::default();
    let mut decoder = decoder(&inputs, &settings);
    let program = "(RULE &copy (input *P *Col))\n(OUT (&copy ^P ^Col))\n(DET &c ColorDomain)\n(RULE &paint (input *P) (&c (:C *Col)))\n(OUT (&paint ^P ^Col))\n";
    let (ends, _) = walk(&mut decoder, &model_tokens(program));
    assert!(matches!(&ends[..], [Consistency::NotConsistent, Consistency::Consistent { assignments }] if assignments.len() == 1), "{ends:?}");
    assert_eq!(decoder.output(), Some(&path(&[4])));
}

/// Inside an `OUT`, the decoder admits only tokens after which some
/// completion passes.
#[test]
fn inside_an_out_the_mask_admits_only_the_tokens_after_which_a_completion_passes() {
    let inputs = inputs(&[1, 2], &[1, 2]);
    let settings = DecodeSettings::default();
    let mut decoder = decoder(&inputs, &settings);
    walk(&mut decoder, &model_tokens(RELATIONS));
    let admits = |decoder: &Decoder<'_>, token: &Token| decoder.vocabulary().id(token).is_some_and(|id| decoder.admissible().contains(id));
    let step = |decoder: &mut Decoder<'_>, token: Token| {
        decoder.step(token).expect("a token in the mask");
    };
    assert!(admits(&decoder, &Token::Control(Control::Out)), "a form may open with `OUT`");
    step(&mut decoder, Token::Control(Control::Out));
    assert!(!admits(&decoder, &Token::Lib(LibName("dir_elem".into()))), "a lib relation");
    assert!(!admits(&decoder, &Token::Fact(FactRelation::ExInput)), "`ex_input`");
    assert!(!admits(&decoder, &Token::Control(Control::Not)), "`NOT`");
    assert!(!admits(&decoder, &Token::Control(Control::End)), "an `OUT` of no atom");
    assert!(admits(&decoder, &Token::Fact(FactRelation::Input)), "`input`");
    // `&colr` holds no Position column to start with.
    assert!(!admits(&decoder, &Token::Relation(2)), "a relation with no Position column");
    assert!(admits(&decoder, &Token::Relation(0)));
    step(&mut decoder, Token::Relation(0));
    assert!(admits(&decoder, &Token::Column(0)), "the Position column");
    assert!(!admits(&decoder, &Token::Column(1)), "the Color column, first");
    step(&mut decoder, Token::Column(0));
    assert!(admits(&decoder, &Token::Control(Control::Key)));
    assert!(!admits(&decoder, &Token::Control(Control::Fresh)));
    assert!(!admits(&decoder, &Token::Control(Control::Zero)));
    step(&mut decoder, Token::Control(Control::Key));
    assert!(admits(&decoder, &Token::Column(1)), "the Color column, second");
    assert!(!admits(&decoder, &Token::Column(0)), "a second Position column");
    assert!(!admits(&decoder, &Token::Control(Control::End)), "one site only");
    step(&mut decoder, Token::Column(1));
    step(&mut decoder, Token::Control(Control::Key));
    assert!(admits(&decoder, &Token::Control(Control::End)));
    assert!(!admits(&decoder, &Token::Column(0)), "a third site");
    assert!(!admits(&decoder, &Token::Relation(0)), "a second atom after two sites");
}

#[test]
fn the_stream_of_an_out_ends_the_program_with_the_out_keyword_its_atoms_and_end() {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let stream = token_stream(&checked(&format!("{RELATIONS}(OUT (&pos ^P) (&colr ^Col))\n")), &vocabulary).expect("the program has a stream");
    let from = stream.iter().position(|(token, _)| *token == Token::Control(Control::Out)).expect("an `OUT` token");
    let want: Vec<(Token, Emitter)> = vec![
        (Token::Control(Control::Out), Emitter::Model),
        (Token::Relation(1), Emitter::Model),
        (Token::Column(0), Emitter::Model),
        (Token::Control(Control::Key), Emitter::Model),
        (Token::Label(0), Emitter::Engine),
        (Token::Relation(2), Emitter::Model),
        (Token::Column(0), Emitter::Model),
        (Token::Control(Control::Key), Emitter::Model),
        (Token::Label(1), Emitter::Engine),
        (Token::Control(Control::End), Emitter::Model),
    ];
    assert_eq!(&stream[from..], &want[..], "the `OUT` form is the last, and declares nothing");
    assert_eq!(Control::Out.text(), "OUT");
    assert!(vocabulary.id(&Token::Control(Control::Out)).is_some());
}

#[test]
fn the_atoms_of_an_out_are_not_exchangeable() {
    let read = |out: &str| {
        let solver = read_solver("out", &format!("{RELATIONS}{out}\n"), "", &|_| None).expect("the file reads").value;
        let Some(arclog::program::Form::Out(out)) = solver.program.value().forms.last().cloned() else { panic!("an `OUT` form") };
        out
    };
    let (one, other) = (read("(OUT (&pos ^P) (&colr ^Col))"), read("(OUT (&colr ^Col) (&pos ^P))"));
    assert_ne!(one, other);
    assert_eq!(one, read("(OUT (&pos ^P) (&colr ^Col))"));
}

/// The rule tests: off, a `RULE` end gives no rule test; on, it gives the
/// verdict of its relation, which ends no decode and changes no mask.
#[test]
fn the_rule_tests_give_the_verdict_of_a_rule_end_and_change_no_mask() {
    let inputs = inputs(&[1, 2], &[1, 2]);
    let off = DecodeSettings::default();
    let on = DecodeSettings { rule_tests: true, ..DecodeSettings::default() };
    let tokens = model_tokens("(RULE &r (input *P *Col))\n(OUT (&r ^P ^Col))\n");
    let (mut with, mut without) = (decoder(&inputs, &on), decoder(&inputs, &off));
    for token in &tokens {
        assert_eq!(with.admissible(), without.admissible(), "the mask before {token:?}");
        let a = with.step(token.clone()).expect("the rule tests change no mask");
        let b = without.step(token.clone()).expect("the stream passes the mask");
        assert!(b.rule_test.is_none(), "with the rule tests off, no `RULE` end runs a test");
        assert_eq!(format!("{:?}", a.consistency), format!("{:?}", b.consistency), "the verdict of the `OUT` is the same");
        if let Some(rule_test) = a.rule_test {
            assert!(matches!(rule_test, Consistency::Consistent { .. }), "{rule_test:?}");
            assert!(with.output().is_none(), "a consistent rule test ends no decode");
        }
    }
    assert!(with.output().is_some() && without.output().is_some());
}

#[test]
fn the_synthesized_program_form_writes_each_site_of_an_out_as_its_column() {
    let inputs = inputs(&[1, 2], &[1, 2]);
    let settings = DecodeSettings::default();
    let mut decoder = decoder(&inputs, &settings);
    walk(&mut decoder, &model_tokens(&format!("{RELATIONS}(OUT (&pos ^P) (&colr ^Col))\n")));
    let written = arclog::write::write_synthesized(decoder.program(), Registry::get());
    assert!(written.contains("(OUT (&r1 ^P) (&r2 ^Col))"), "{written}");
}
