//! The token stream of each program of `docs/arclog/arclog.md#trace-form`
//! gives the tokens of its trace form, the bracketed ones the engine's, and
//! a program that passes a vocabulary cap is refused.

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::diagnostic::DiagnosticKind;
use arclog::program::{ConstraintOp, FactRelation};
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::resolve;
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, Vocabulary, VocabularyCaps};

/// The checked program of the concept case of the arclog file `arclog`.
fn checked(arclog: &str) -> CheckedProgram {
    let solver = read_solver("stream", arclog, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    check_program(program, &clauses, registry, &mut CheckCache::default()).expect("every check passes")
}

/// The stream of `arclog` under the default settings.
fn stream(arclog: &str) -> Vec<(Token, Emitter)> {
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    token_stream(&checked(arclog), &vocabulary).expect("the program has a stream")
}

const BG: &str = "(RULE &bg (input (:Col *C)))\n";
const FG: &str = "(RULE &fg (input *P *Col) (&bg (:C *V)) (!= Col V))\n";

use Emitter::{Engine as E, Model as M};

fn control(control: Control) -> Token {
    Token::Control(control)
}

/// `*` and the engine's echo of label slot `label`.
fn fresh(label: u32) -> [(Token, Emitter); 2] {
    [(control(Control::Fresh), M), (Token::Label(label), E)]
}

/// The tokens of `stream` after the first `skip`.
fn after(stream: &[(Token, Emitter)], skip: usize) -> &[(Token, Emitter)] {
    &stream[skip..]
}

/// The count of the tokens of the stream of `arclog`.
fn length(arclog: &str) -> usize {
    stream(arclog).len()
}

#[test]
fn a_rule_gives_its_atoms_its_constraint_and_its_declaration() {
    let prefix = length(BG);
    let got = stream(&format!("{BG}{FG}"));
    let mut want = vec![(control(Control::Rule), M), (Token::Fact(FactRelation::Input), M), (Token::Column(0), M)];
    want.extend(fresh(0));
    want.push((Token::Column(1), M));
    want.extend(fresh(1));
    want.extend([(Token::Relation(0), M), (Token::Column(0), M)]);
    want.extend(fresh(2));
    want.extend([
        (control(Control::Op(ConstraintOp::Ne)), M),
        (Token::Label(1), M),
        (Token::Label(2), M),
        (control(Control::End), M),
        (Token::Relation(1), E),
    ]);
    assert_eq!(after(&got, prefix), &want[..]);
}

#[test]
fn an_instance_gives_its_input_names_its_projection_and_its_outputs() {
    let program = format!("{BG}{FG}");
    let prefix = length(&program);
    let got = stream(&format!("{program}(INIT &comps Connectivity (node ((:P P)) (&fg *P)))\n"));
    let mut want = vec![
        (control(Control::Init), M),
        (Token::Lib(LibName("Connectivity".into())), M),
        (Token::Column(0), E),
        (control(Control::Skip), M),
        (Token::Column(1), E),
        (Token::Relation(1), M),
        (Token::Column(0), M),
    ];
    want.extend(fresh(0));
    want.extend([
        (control(Control::End), M),
        (Token::Column(0), E),
        (control(Control::End), M),
        (Token::Column(1), E),
        (Token::Label(0), M),
        (control(Control::End), M),
        (Token::Column(2), E),
        (control(Control::Skip), M),
    ]);
    want.extend((2..7).map(|slot| (Token::Relation(slot), E)));
    assert_eq!(after(&got, prefix), &want[..]);
}

#[test]
fn an_or_gives_its_branches_between_or_tokens_and_its_end() {
    let program = "(RULE &axis_len (input (:P *B)) (frame_extent (:P B) (:N *N)))\n(RULE &larger (&axis_len *B) (&axis_len (:B *B2)))\n";
    let prefix = length(program);
    let got = stream(&format!("{program}(RULE &prior (&axis_len *B *N) (&axis_len (:B *B2) (:N *N2)) (OR ((> N N2)) ((= N N2) (&larger B B2))))\n"));
    let mut want = vec![(control(Control::Rule), M), (Token::Relation(0), M), (Token::Column(0), M)];
    want.extend(fresh(0));
    want.push((Token::Column(1), M));
    want.extend(fresh(1));
    want.extend([(Token::Relation(0), M), (Token::Column(0), M)]);
    want.extend(fresh(2));
    want.push((Token::Column(1), M));
    want.extend(fresh(3));
    want.extend([
        (control(Control::Or), M),
        (control(Control::Op(ConstraintOp::Gt)), M),
        (Token::Label(1), M),
        (Token::Label(3), M),
        (control(Control::Or), M),
        (control(Control::Op(ConstraintOp::Eq)), M),
        (Token::Label(1), M),
        (Token::Label(3), M),
        (Token::Relation(1), M),
        (Token::Column(0), M),
        (Token::Label(0), M),
        (Token::Column(1), M),
        (Token::Label(2), M),
        (control(Control::End), M),
        (control(Control::End), M),
        (Token::Relation(2), E),
    ]);
    assert_eq!(after(&got, prefix), &want[..]);
}

#[test]
fn a_program_past_a_cap_is_refused() {
    let mut settings = DecodeSettings::default();
    settings.vocabulary = VocabularyCaps { relations: 1, ..settings.vocabulary };
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let refusal = token_stream(&checked(&format!("{BG}{FG}")), &vocabulary).expect_err("the second relation passes the cap");
    assert_eq!(refusal.kind, DiagnosticKind::Bound);
}
