//! The mask admits a constraint's operator, or its first label, only where
//! some completion of the constraint passes every check, and a token in a
//! projection of an instance input only where some completion of the
//! projection passes, and a field's column token on a body site only where
//! some label after it passes.

use arclog::decode::{Decoder, Refusal};
use arclog::eval::instance::Constructions;
use arclog::eval::values::Caps;
use arclog::program::{ConstraintOp, FactRelation};
use arclog::registry::{LibName, Registry};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{Control, DecodeSettings, Token};
use arclog::task::Task;

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

fn step_all(decoder: &mut Decoder<'_>, tokens: &[Token]) {
    for token in tokens {
        decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{token:?}: {refusal:?}"));
    }
}

fn admits(decoder: &Decoder<'_>, token: &Token) -> bool {
    decoder.admissible().contains(decoder.vocabulary().id(token).expect("a token of the vocabulary"))
}

/// The tokens of the vocabulary that the mask of `decoder` admits.
fn admitted(decoder: &Decoder<'_>) -> Vec<Token> {
    let vocabulary = decoder.vocabulary();
    let mask = decoder.admissible();
    (0..u32::try_from(vocabulary.len()).expect("fewer than 2^32 tokens")).filter(|id| mask.contains(*id)).map(|id| vocabulary.token(id).expect("an id").clone()).collect()
}

const ORDERS: [ConstraintOp; 4] = [ConstraintOp::Lt, ConstraintOp::Le, ConstraintOp::Gt, ConstraintOp::Ge];

/// The state in a `RULE` body after `(input *P *Col)`: labels `P` and
/// `Col`, none of a type with an order.
fn body_with_labels(inputs: &Inputs) -> Decoder<'_> {
    let mut decoder = decoder(inputs);
    let fresh = Token::Control(Control::Fresh);
    step_all(&mut decoder, &[Token::Control(Control::Rule), Token::Fact(FactRelation::Input), Token::Column(0), fresh.clone(), Token::Column(1), fresh]);
    decoder
}

#[test]
fn an_operator_with_no_label_in_scope_is_refused() {
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    step_all(&mut decoder, &[Token::Control(Control::Rule)]);
    for op in ORDERS {
        assert!(!admits(&decoder, &Token::Control(Control::Op(op))), "{op:?} with no label in scope");
        assert!(matches!(decoder.fork().step(Token::Control(Control::Op(op))), Err(Refusal::Check { .. } | Refusal::Grammar(_))));
    }
}

#[test]
fn an_order_operator_over_labels_with_no_order_is_refused() {
    let inputs = inputs();
    let decoder = body_with_labels(&inputs);
    for op in ORDERS {
        assert!(!admits(&decoder, &Token::Control(Control::Op(op))), "{op:?} over a position and a color");
    }
    assert!(admits(&decoder, &Token::Control(Control::Op(ConstraintOp::Ne))));
    assert!(admits(&decoder, &Token::Control(Control::Op(ConstraintOp::Eq))));
}

/// Every operator and first label the mask admits has an admitted token
/// after it, and the first label of an operator other than `=` has an
/// admitted second operand.
#[test]
fn each_admitted_operator_and_first_label_has_an_admitted_continuation() {
    let inputs = inputs();
    let decoder = body_with_labels(&inputs);
    let ops = [ConstraintOp::Eq, ConstraintOp::Ne, ConstraintOp::Lt, ConstraintOp::Le, ConstraintOp::Gt, ConstraintOp::Ge];
    let mut firsts = 0;
    for op in ops {
        let operator = Token::Control(Control::Op(op));
        if !admits(&decoder, &operator) {
            continue;
        }
        let mut after_op = decoder.fork();
        after_op.step(operator).expect("an admitted operator");
        let labels = admitted(&after_op);
        assert!(!labels.is_empty(), "the mask is empty after {op:?}");
        for first in labels {
            let mut after_first = after_op.fork();
            after_first.step(first.clone()).expect("an admitted first label");
            assert!(!admitted(&after_first).is_empty(), "the mask is empty after {op:?} {first:?}");
            firsts += 1;
        }
    }
    assert!(firsts > 0, "the mask admits a constraint");
}

fn lib(name: &str) -> Token {
    Token::Lib(LibName(name.into()))
}

/// The tokens of `(dir_elem <label>)`, which makes one label, of the type `Dir`.
fn dir_label(label: Control) -> Vec<Token> {
    vec![lib("dir_elem"), Token::Column(0), Token::Control(label)]
}

/// The decode after an `INIT` of `component` whose key is `(dir_elem
/// <key>)`, and the body `(dir_elem *D)` of its first input, without its
/// `END`; or none where the mask refuses one of them.
fn instance_with_body<'a>(inputs: &'a Inputs, component: &str, key: Control) -> Option<Decoder<'a>> {
    let mut decoder = decoder(inputs);
    let tokens = [Token::Control(Control::Init), lib(component)].into_iter().chain(dir_label(key)).chain([Token::Control(Control::End)]).chain(dir_label(Control::Fresh));
    for token in tokens {
        decoder.step(token).ok()?;
    }
    Some(decoder)
}

/// Every token that the mask admits in the projection of an input has an
/// admitted token after it, down to four tokens, whether the key makes a key
/// label or not: a field's column token on a column of a type parameter
/// is admitted only where some label follows it.
#[test]
fn each_admitted_token_in_a_projection_has_an_admitted_continuation() {
    fn walk(decoder: &Decoder<'_>, path: &mut Vec<Token>, depth: usize, walked: &mut usize) {
        for token in admitted(decoder) {
            let mut next = decoder.fork();
            next.step(token.clone()).expect("an admitted token");
            path.push(token.clone());
            assert!(!admitted(&next).is_empty(), "the mask is empty after {path:?}");
            *walked += 1;
            if depth > 0 {
                walk(&next, path, depth - 1, walked);
            }
            path.pop();
        }
    }
    let inputs = inputs();
    let mut walked = 0;
    for component in ["BoundingBox", "Order"] {
        for key in [Control::Fresh, Control::Key] {
            let Some(mut decoder) = instance_with_body(&inputs, component, key) else { continue };
            if decoder.step(Token::Control(Control::End)).is_ok() {
                walk(&decoder, &mut vec![], 3, &mut walked);
            }
        }
    }
    assert!(walked > 0, "a projection with admitted tokens");
}

/// Steps the tokens that `text` names, which the model writes, and skips each one the engine emitted.
fn step_text(decoder: &mut Decoder<'_>, text: &str) {
    let vocabulary = decoder.vocabulary();
    let by_name: std::collections::HashMap<String, Token> = (0..u32::try_from(vocabulary.len()).unwrap()).map(|id| vocabulary.token(id).unwrap().clone()).map(|token| (token.to_string(), token)).collect();
    let mut queue: Vec<Token> = vec![];
    for name in text.split_whitespace() {
        let token = by_name.get(name).unwrap_or_else(|| panic!("no token {name}")).clone();
        if queue.first() == Some(&token) {
            queue.remove(0);
            continue;
        }
        let step = decoder.step(token.clone()).unwrap_or_else(|refusal| panic!("{name}: {refusal:?}"));
        queue = step.forced.to_vec();
    }
}

const CARDINALITY: &str = "INIT Cardinality &r0 &r1 &r2 :0 input :0 * L0 :1 ^ L1 END :1 input :0 * L2 :1 L1 END :0 END :1 L2 END :2 SKIP :2 SKIP";

/// A field's column token on the site of a body atom is admitted only where
/// some label after it passes. `&r0` is an output of `Cardinality` whose
/// first column holds a record, and a rule's head site there takes the
/// field `:0` with `*`.
#[test]
fn a_field_token_whose_label_passes_is_admitted() {
    let inputs = inputs();
    let mut decoder = decoder(&inputs);
    step_text(&mut decoder, CARDINALITY);
    step_text(&mut decoder, "RULE &r0 :0");
    assert!(admits(&decoder, &Token::Column(0)));
}
