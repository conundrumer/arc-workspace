//! The token stream of each program of `docs/arclog/arclog.md#trace-form`
//! gives the tokens of its trace form, the bracketed ones the engine's, a
//! site on a record-valued column gives one `END`, after its field sites, and
//! a program that passes a vocabulary cap is refused.

use std::sync::Arc;

use arclog::check::{check_program, check_shared_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::diagnostic::DiagnosticKind;
use arclog::program::{ConstraintOp, FactRelation};
use arclog::read::read_solver;
use arclog::registry::{LibName, Registry};
use arclog::resolver::{resolve, resolve_cases};
use arclog::stream::{token_stream, Control, DecodeSettings, Emitter, Token, TokenKind, Vocabulary, VocabularyCaps};

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
fn an_instance_gives_its_outputs_its_input_names_and_its_projection() {
    let program = format!("{BG}{FG}");
    let prefix = length(&program);
    let got = stream(&format!("{program}(INIT &comps Connectivity (node ((:P P)) (&fg *P)))\n"));
    let mut want = vec![
        (control(Control::Init), M),
        (Token::Lib(LibName("Connectivity".into())), M),
        (Token::Relation(2), E),
        (Token::Relation(3), E),
        (Token::Relation(4), E),
        (Token::Relation(5), E),
        (Token::Column(0), E),
        (control(Control::Skip), M),
        (Token::Column(1), E),
        (Token::Relation(1), M),
        (Token::Column(1), M),
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
    assert_eq!(after(&got, prefix), &want[..]);
}

/// An `Unfold` instance whose `step` input reads the instance's own
/// output `take`.
const WALK: &str = "(INIT &walk Unfold
  (start ((:t B)) (&bg (:C *B)))
  (initial_taken ((:item B)) (&bg (:C *B)))
  (initial_untaken ((:item B)) (&bg (:C *B)))
  (step ((:t B) (:t2 X)) (&bg (:C *B)) (&bg (:C *X)) (&walk.take (:t B) (:item X))))
";

#[test]
fn an_input_that_reads_its_instances_output_reads_a_relation_the_stream_declared() {
    let got = stream(&format!("{BG}{WALK}"));
    let declared: Vec<usize> = got.iter().enumerate().filter(|(_, (token, emitter))| matches!(token, Token::Relation(_)) && *emitter == E).map(|(at, _)| at).collect();
    let read = got.iter().rposition(|(token, emitter)| matches!(token, Token::Relation(_)) && *emitter == M).expect("the step reads an output");
    assert!(declared.iter().all(|at| *at < read), "every declaration stands before the read: {declared:?} and {read}");
}

#[test]
fn an_or_gives_its_branches_between_also_tokens_and_its_end() {
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
        (control(Control::Also), M),
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

const BBOX: &str = "(INIT &bbox BoundingBox\n  (key ((input *P ^Col))\n    (cell (P)\n      (input *P Col))))\n";

#[test]
fn a_site_on_a_record_gives_its_field_sites_and_one_end() {
    let prefix = length(BBOX);
    let got = stream(&format!("{BBOX}(RULE &w (&bbox.cell (:key (:Col *Col)) *P))\n"));
    let elided = stream(&format!("{BBOX}(RULE &w (&bbox.cell (:key *Col) *P))\n"));
    let mut want = vec![(control(Control::Rule), M), (Token::Relation(1), M), (Token::Column(0), M), (Token::Column(0), M)];
    want.extend(fresh(0));
    want.extend([(control(Control::End), M), (Token::Column(1), M)]);
    want.extend(fresh(1));
    want.extend([(control(Control::End), M), (Token::Relation(2), E)]);
    assert_eq!(after(&got, prefix), &want[..]);
    assert_eq!(got, elided);
}

#[test]
fn a_case_program_from_alts_is_written_after_what_its_forms_read() {
    let alts = "(RULE &fill (input *P))\n\n(ALTS $choice \"whether &fill reads &box\" $Plain\n  (ALT $Boxed\n    (RULE &box (input *P))\n    (RULE &fill (&box *P))))\n";
    let solver = read_solver("alts", alts, "", &|_| None).expect("the file reads").value;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let boxed = cases.cases().find(|resolved| resolved.case.name != cases.concept().case.name).expect("the case of `$Boxed`");
    let program = check_shared_program(Arc::clone(&boxed.resolved.value), &clauses, registry, &mut CheckCache::default()).expect("every check passes");
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let got = token_stream(&program, &vocabulary).expect("the case program has a stream");
    assert_eq!(got, stream("(RULE &box (input *P))\n(RULE &fill (&box *P))\n"));
}

#[test]
fn a_vocabulary_gives_the_kind_of_each_token() {
    let registry = Registry::get();
    let vocabulary = Vocabulary::new(registry, &DecodeSettings::default());
    let kind = |token: Token| vocabulary.kind(vocabulary.id(&token).expect("the vocabulary holds the token"));
    let lib = |name: &str| Token::Lib(LibName(name.into()));
    assert_eq!(kind(Token::Control(Control::Rule)), Some(TokenKind::Control));
    assert_eq!(kind(lib("compose")), Some(TokenKind::LibRelation));
    assert_eq!(kind(lib("Cardinality")), Some(TokenKind::Component));
    assert_eq!(kind(Token::Proposer(LibName("AxisDomain".into()))), Some(TokenKind::Proposer));
    assert_eq!(kind(Token::Fact(FactRelation::Input)), Some(TokenKind::Fact));
    assert_eq!(kind(Token::Relation(0)), Some(TokenKind::Relation));
    assert_eq!(kind(Token::Column(0)), Some(TokenKind::Column));
    assert_eq!(kind(Token::Label(0)), Some(TokenKind::Label));
    assert_eq!(vocabulary.kind(vocabulary.len() as u32), None);
    let macros = (0..vocabulary.len() as u32).filter(|&id| vocabulary.kind(id) == Some(TokenKind::RelationMacro)).count();
    let defined = registry.names().filter(|name| matches!(registry.entry(name), Some(arclog::registry::LibEntry::Macro(_)))).count();
    assert_eq!(macros, defined);
}
