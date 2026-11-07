//! The tokens of a stream, one variant per token set of
//! `docs/engine/arclog-stream.md#token-stream`, and which side emits each token.

use std::fmt;

use crate::program::{ConstraintOp, FactRelation};
use crate::read::spelling::{self as sp, spelling};
use crate::registry::LibName;

/// A token of the stream.
///
/// `Display` writes the token's name, its spelling in
/// `docs/engine/arclog-stream.md#token-stream`: a control token its text, a lib
/// relation, relation macro, component or proposer its name, a fact
/// relation its name, and a relation, column or label, which has no text,
/// `&r<slot>`, `:<position>` or `L<slot>`. The names of the tokens of one
/// vocabulary are distinct.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum Token {
    Control(Control),
    /// A lib relation, a relation macro or a component.
    Lib(LibName),
    Proposer(LibName),
    Fact(FactRelation),
    /// A relation the program declares, by the slot the engine assigned at
    /// its declaration, in order of declaration.
    Relation(u32),
    /// A column of a relation, an input of a component or a named clause
    /// of a form, by its position.
    Column(u32),
    /// A label of the current label scope, in order of creation.
    Label(u32),
}

/// The kind of a token: the token set of
/// `docs/engine/arclog-stream.md#token-stream` that it belongs to, with that doc's
/// set of lib relations, relation macros and components split by the
/// registry's entry.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum TokenKind {
    Control,
    LibRelation,
    RelationMacro,
    Component,
    Proposer,
    Fact,
    Relation,
    Column,
    Label,
}

impl TokenKind {
    /// The spelling of the kind: `control`, `lib relation`, `relation macro`,
    /// `component`, `proposer`, `fact relation`, `relation`, `column` or
    /// `label`.
    pub fn spelling(self) -> &'static str {
        match self {
            TokenKind::Control => "control",
            TokenKind::LibRelation => "lib relation",
            TokenKind::RelationMacro => "relation macro",
            TokenKind::Component => "component",
            TokenKind::Proposer => "proposer",
            TokenKind::Fact => "fact relation",
            TokenKind::Relation => "relation",
            TokenKind::Column => "column",
            TokenKind::Label => "label",
        }
    }
}

/// A control token.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Control {
    Rule,
    Det,
    Init,
    One,
    /// `SET`, the mark of a `DET` whose one value is its proposers' whole set of rows.
    Set,
    Choose,
    RigidDet,
    /// `OUT`, the keyword of the form that selects the output's two columns.
    Out,
    Or,
    If,
    All,
    End,
    Skip,
    Also,
    Not,
    /// `*`, which makes the label the engine echoes after it.
    Fresh,
    /// `^`, which makes a key column of the label the engine echoes after
    /// it.
    Key,
    /// `0`.
    Zero,
    Op(ConstraintOp),
    /// `DEMONSTRATED`, the keyword of the form of `docs/arclog/arclog.md#demonstrated`.
    Demonstrated,
    /// `DEMO_RULE`, the keyword of a demonstrated rule of a `DEMONSTRATED` form.
    DemoRule,
    /// `PREDICT`, the keyword of a `DEMO_RULE`'s `&prediction` clause.
    Predict,
    /// `ALT_FORM`, which marks the next form of a `DEMO_RULE` as one that an
    /// `ALT` gives it, a label scope of its own.
    AltForm,
}

impl fmt::Display for Token {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Token::Control(control) => f.write_str(control.text()),
            Token::Lib(LibName(name)) | Token::Proposer(LibName(name)) => write!(f, "{name}"),
            Token::Fact(fact) => f.write_str(&fact.spelled()),
            Token::Relation(slot) => write!(f, "&r{slot}"),
            Token::Column(position) => write!(f, ":{position}"),
            Token::Label(slot) => write!(f, "L{slot}"),
        }
    }
}

impl Control {
    /// The text of the control token.
    pub fn text(self) -> &'static str {
        match self {
            Control::Rule => "RULE",
            Control::Det => "DET",
            Control::Init => "INIT",
            Control::One => "ONE",
            Control::Set => "SET",
            Control::Choose => "CHOOSE",
            Control::RigidDet => "RIGID_DET",
            Control::Out => "OUT",
            Control::Or => "OR",
            Control::If => "IF",
            Control::All => "ALL",
            Control::End => "END",
            Control::Skip => "SKIP",
            Control::Also => "ALSO",
            Control::Not => "NOT",
            Control::Fresh => "*",
            Control::Key => "^",
            Control::Zero => "0",
            Control::Op(op) => spelling(sp::CONSTRAINT_OPS, &op),
            Control::Demonstrated => "DEMONSTRATED",
            Control::DemoRule => "DEMO_RULE",
            Control::Predict => "PREDICT",
            Control::AltForm => "ALT_FORM",
        }
    }

    /// Every control token, in the order of the vocabulary's slots.
    pub const ALL: [Control; 24] = [
        Control::Rule,
        Control::Det,
        Control::Init,
        Control::One,
        Control::Set,
        Control::Choose,
        Control::RigidDet,
        Control::Out,
        Control::Or,
        Control::If,
        Control::All,
        Control::End,
        Control::Skip,
        Control::Also,
        Control::Not,
        Control::Fresh,
        Control::Key,
        Control::Zero,
        Control::Op(ConstraintOp::Eq),
        Control::Op(ConstraintOp::Ne),
        Control::Op(ConstraintOp::Lt),
        Control::Op(ConstraintOp::Le),
        Control::Op(ConstraintOp::Gt),
        Control::Op(ConstraintOp::Ge),
    ];

    /// The control tokens of the `DEMONSTRATED` form, whose slots follow
    /// every other slot of the vocabulary, in this order. The vocabulary
    /// holds them so that no token id changes. The grammar refuses each of
    /// them at every state (`crate::decode`), and the writer gives no stream
    /// for a program that holds the form.
    pub const DEMONSTRATED_FORM: [Control; 4] = [Control::Demonstrated, Control::DemoRule, Control::Predict, Control::AltForm];
}

/// Which side emits a token: the language model, or the engine, as the
/// forced tokens of `docs/engine/arclog-stream.md#token-stream` are.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Emitter {
    Model,
    Engine,
}
