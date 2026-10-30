//! The trace form of `docs/arclog/arclog.md#trace-form`. The renderer reads a
//! trace and changes nothing in it.
//!
//! The trace form parses the stream the records give, by the grammar that
//! [`crate::stream::token_stream`] writes, and prints the tree of the program
//! with the engine's tokens in brackets. It prints a `RULE`, `DET`, `INIT` and
//! `OUT` form; the tokens of any other form stand on one line, in the order
//! of the stream, the engine's in brackets.

use std::collections::BTreeMap;

use super::label_names::label_name;
use super::{DecodeRecord, DecodeTrace, TopK};
use crate::program::{column_spelled, RelationRef};
use crate::read::spelling::{self as sp, spelling};
use crate::registry::{Component, Registry};
use crate::resolver::registry_columns::{component, typed_columns};
use crate::stream::{Control, Emitter, Token, Vocabulary};

/// What the trace form shows.
#[derive(Clone, Debug, Default)]
pub struct TraceFormOptions {
    /// Shows the language model's top-k tokens after the symbol of their
    /// decision, in braces, each with its probability.
    pub top_k: bool,
    /// The name of the relation declared at each relation slot, such as
    /// `&fg`, or `&comps.component` for an output of an instance.
    /// A slot `n` with no name here is written `&rn`.
    pub relations: Vec<String>,
}

/// The trace form of `trace`: each form's tree, one form after another, the
/// tokens the engine emitted in brackets, and, with `options.top_k`, the top-k
/// tokens that the records hold.
pub fn trace_form(trace: &DecodeTrace, vocabulary: &Vocabulary, options: &TraceFormOptions) -> String {
    let mut renderer = Renderer {
        records: trace.records(),
        at: 0,
        registry: vocabulary.registry(),
        options,
        labels: Vec::new(),
        made: Vec::new(),
        depth: 0,
        in_form: false,
        columns: BTreeMap::new(),
    };
    let mut lines = Vec::new();
    while renderer.peek().is_some() {
        lines.extend(renderer.form());
    }
    let mut text = lines.join("\n");
    text.push('\n');
    text
}

/// A printed piece: its lines, the first without the indent of its place.
type Block = Vec<String>;

struct Renderer<'a> {
    records: Vec<&'a DecodeRecord>,
    at: usize,
    registry: &'a Registry,
    options: &'a TraceFormOptions,
    /// The name of each label slot of the form, in the order of the slots.
    labels: Vec<String>,
    /// The names of the labels the clause body makes, in order.
    made: Vec<String>,
    /// How deep the conjunct being read stands in the clause's body.
    depth: usize,
    /// Whether the body being read is a body of an `INIT` form, whose reads
    /// of a declared relation take the Example column first.
    in_form: bool,
    /// The column names of each declared relation, by slot.
    columns: BTreeMap<u32, Vec<String>>,
}

impl<'a> Renderer<'a> {
    fn peek(&self) -> Option<&'a DecodeRecord> {
        self.records.get(self.at).copied()
    }

    fn next(&mut self) -> Option<&'a DecodeRecord> {
        let record = self.peek()?;
        self.at += 1;
        Some(record)
    }

    fn peek_control(&self) -> Option<Control> {
        match self.peek()? {
            DecodeRecord { token: Token::Control(control), emitter: Emitter::Model, .. } => Some(*control),
            _ => None,
        }
    }

    fn take_control(&mut self, control: Control) -> Option<&'a DecodeRecord> {
        (self.peek_control() == Some(control)).then(|| self.next()).flatten()
    }

    /// The text of `record`'s token, with its top-k braces.
    fn symbol(&self, record: &DecodeRecord, text: &str) -> String {
        match (&record.top_k, self.options.top_k) {
            (Some(top_k), true) => format!("{text}{}", self.braces(top_k)),
            _ => text.to_owned(),
        }
    }

    fn braces(&self, top_k: &TopK) -> String {
        let shown: Vec<String> = top_k.0.iter().map(|(token, probability)| format!("{} {}", self.spell(token, None), probability_text(*probability))).collect();
        format!("{{{}}}", shown.join(" "))
    }

    /// The spelling of `token`, with `columns` the columns of the relation
    /// whose site is being read.
    fn spell(&self, token: &Token, columns: Option<&[String]>) -> String {
        match token {
            Token::Control(_) | Token::Lib(_) | Token::Proposer(_) | Token::Fact(_) => token.to_string(),
            Token::Relation(slot) => self.relation_name(*slot),
            Token::Column(position) => columns.and_then(|columns| columns.get(*position as usize)).map_or_else(|| token.to_string(), |name| format!(":{name}")),
            Token::Label(slot) => self.labels.get(*slot as usize).cloned().unwrap_or_else(|| Token::Label(*slot).to_string()),
        }
    }

    /// The bracket of the relations `slots` the engine declares.
    fn declared_bracket(&self, slots: &[u32]) -> String {
        format!("[{}]", slots.iter().map(|slot| self.relation_name(*slot)).collect::<Vec<_>>().join(" "))
    }

    /// The text of the token of `record`: the language model's with its
    /// top-k braces, the engine's in brackets.
    fn shown(&self, record: &DecodeRecord) -> String {
        let text = self.spell(&record.token, None);
        match record.emitter {
            Emitter::Model => self.symbol(record, &text),
            Emitter::Engine => format!("[{text}]"),
        }
    }

    fn relation_name(&self, slot: u32) -> String {
        self.options.relations.get(slot as usize).cloned().unwrap_or_else(|| Token::Relation(slot).to_string())
    }

    fn form(&mut self) -> Block {
        self.labels.clear();
        self.made.clear();
        self.depth = 0;
        self.in_form = false;
        match self.peek_control() {
            Some(control @ (Control::Rule | Control::Det)) => self.clause(control),
            Some(Control::Init) => self.instance(),
            Some(Control::Out) => self.out(),
            _ => self.flat(),
        }
    }

    /// The tokens up to the next form keyword, on one line.
    fn flat(&mut self) -> Block {
        let mut words = Vec::new();
        while let Some(record) = self.next() {
            words.push(self.shown(record));
            if matches!(self.peek_control(), Some(Control::Rule | Control::Det | Control::Init | Control::Choose | Control::RigidDet | Control::Out)) {
                break;
            }
        }
        vec![words.join(" ")]
    }

    /// An `OUT` form: its atoms, then its `END`. It declares no relation.
    fn out(&mut self) -> Block {
        let record = self.next().expect("the keyword");
        let mut pieces = self.conjuncts(&[Control::End]);
        if let Some(end) = self.take_control(Control::End) {
            pieces.push(vec![self.symbol(end, "END")]);
        }
        hang(&format!("({} ", self.symbol(record, Control::Out.text())), pieces, ")")
    }

    fn clause(&mut self, keyword: Control) -> Block {
        let record = self.next().expect("the keyword");
        let mut pieces: Vec<Block> = Vec::new();
        while let Some(DecodeRecord { token: Token::Proposer(name), emitter: Emitter::Model, .. }) = self.peek() {
            let record = self.next().expect("the proposer");
            pieces.push(vec![self.symbol(record, &name.0)]);
        }
        pieces.extend(self.conjuncts(&[Control::Set, Control::One, Control::End]));
        if let Some(set) = self.take_control(Control::Set) {
            pieces.push(vec![self.symbol(set, "SET")]);
        }
        while let Some(one) = self.take_control(Control::One) {
            let mut words = vec![self.symbol(one, "ONE")];
            while let Some(DecodeRecord { token: Token::Label(slot), emitter: Emitter::Model, .. }) = self.peek() {
                self.next();
                words.push(self.spell(&Token::Label(*slot), None));
            }
            if let Some(end) = self.take_control(Control::End) {
                words.push(self.symbol(end, "END"));
            }
            pieces.push(vec![words.join(" ")]);
        }
        if let Some(end) = self.take_control(Control::End) {
            pieces.push(vec![self.symbol(end, "END")]);
        }
        let mut lines = hang(&format!("({} ", self.symbol(record, keyword.text())), pieces, ")");
        let declared = self.declarations();
        if let Some(slot) = declared.first() {
            self.columns.insert(*slot, self.made.clone());
            lines.push(self.declared_bracket(&declared));
        }
        lines
    }

    /// The relation tokens that the engine emits next.
    fn declarations(&mut self) -> Vec<u32> {
        let mut slots = Vec::new();
        while let Some(DecodeRecord { token: Token::Relation(slot), emitter: Emitter::Engine, .. }) = self.peek() {
            self.next();
            slots.push(*slot);
        }
        slots
    }

    /// The conjuncts up to a model control token in `stops`, or the end of
    /// the trace.
    fn conjuncts(&mut self, stops: &[Control]) -> Vec<Block> {
        let mut blocks = Vec::new();
        while self.peek().is_some() && !self.peek_control().is_some_and(|control| stops.contains(&control)) {
            blocks.push(self.conjunct());
        }
        blocks
    }

    fn conjunct(&mut self) -> Block {
        let record = self.peek().expect("a token");
        match (&record.token, record.emitter) {
            (Token::Fact(_) | Token::Lib(_) | Token::Proposer(_) | Token::Relation(_), Emitter::Model) => vec![self.atom()],
            (Token::Control(Control::Not), Emitter::Model) => {
                self.next();
                let inner = match self.peek().map(|record| &record.token) {
                    Some(Token::Fact(_) | Token::Lib(_) | Token::Proposer(_) | Token::Relation(_)) => vec![self.atom()],
                    _ => self.conjunct(),
                };
                hang(&format!("({} ", self.symbol(record, "NOT")), vec![inner], ")")
            }
            (Token::Control(Control::Op(op)), Emitter::Model) => {
                self.next();
                let first = self.operand();
                let second = self.operand();
                vec![format!("({} {first} {second})", self.symbol(record, spelling(sp::CONSTRAINT_OPS, op)))]
            }
            (Token::Control(Control::Or), Emitter::Model) => self.disjunction(),
            (Token::Control(Control::If), Emitter::Model) => self.lists(3, "IF"),
            (Token::Control(Control::All), Emitter::Model) => self.lists(2, "ALL"),
            _ => {
                self.next();
                vec![self.shown(record)]
            }
        }
    }

    fn disjunction(&mut self) -> Block {
        let or = self.next().expect("OR");
        let mut pieces = Vec::new();
        loop {
            self.depth += 1;
            let branch = self.conjuncts(&[Control::Also, Control::End]);
            self.depth -= 1;
            pieces.push(hang("(", branch, ")"));
            if let Some(also) = self.take_control(Control::Also) {
                pieces.push(vec![self.symbol(also, "ALSO")]);
                continue;
            }
            if let Some(end) = self.take_control(Control::End) {
                pieces.push(vec![self.symbol(end, "END")]);
            }
            break;
        }
        hang(&format!("({} ", self.symbol(or, "OR")), pieces, ")")
    }

    /// An `IF` or an `ALL` form: `count` lists, each followed by its `END`.
    fn lists(&mut self, count: usize, name: &str) -> Block {
        let keyword = self.next().expect("the keyword");
        let mut pieces = Vec::new();
        for _ in 0..count {
            self.depth += 1;
            let body = self.conjuncts(&[Control::End]);
            self.depth -= 1;
            let mut list = hang("(", body, ")");
            if let Some(end) = self.take_control(Control::End) {
                let last = list.last_mut().expect("a line");
                *last = format!("{last} {}", self.symbol(end, "END"));
            }
            pieces.push(list);
        }
        hang(&format!("({} ", self.symbol(keyword, name)), pieces, ")")
    }

    /// An operand of a constraint: a label, a fresh label, or `0`.
    fn operand(&mut self) -> String {
        match self.peek().map(|record| (&record.token, record.emitter)) {
            Some((Token::Label(slot), Emitter::Model)) => {
                let record = self.next().expect("the label");
                let text = self.spell(&Token::Label(*slot), None);
                self.symbol(record, &text)
            }
            Some((Token::Control(Control::Zero), Emitter::Model)) => {
                let record = self.next().expect("0");
                self.symbol(record, "0")
            }
            Some((Token::Control(mark @ (Control::Fresh | Control::Key)), Emitter::Model)) => self.mark("V", *mark),
            _ => String::new(),
        }
    }

    /// A `*` or `^` and the label the engine echoes after it, a new label
    /// named from `base`.
    fn mark(&mut self, base: &str, mark: Control) -> String {
        let record = self.next().expect("the mark");
        let symbol = self.symbol(record, mark.text());
        match self.peek() {
            Some(DecodeRecord { token: Token::Label(slot), emitter: Emitter::Engine, .. }) => {
                self.next();
                let name = self.fresh_name(base);
                if *slot as usize == self.labels.len() {
                    self.labels.push(name.clone());
                    if self.depth == 0 {
                        self.made.push(name.clone());
                    }
                }
                let shown = self.spell(&Token::Label(*slot), None);
                format!("{symbol}[{shown}]")
            }
            _ => symbol,
        }
    }

    /// `base`, PascalCase, with the least digit suffix from 2 that no label
    /// of the form has taken.
    fn fresh_name(&self, base: &str) -> String {
        label_name(base, |name| self.labels.iter().any(|label| label == name))
    }

    fn atom(&mut self) -> String {
        let record = self.next().expect("the relation");
        let columns = self.relation_columns(&record.token);
        let text = self.spell(&record.token, None);
        let mut atom = format!("({}", self.symbol(record, &text));
        while let Some(DecodeRecord { token: Token::Column(position), emitter: Emitter::Model, .. }) = self.peek() {
            let site = self.next().expect("the column");
            let column = columns.get(*position as usize).cloned().unwrap_or_else(|| position.to_string());
            atom.push_str(&format!(" ({}", self.symbol(site, &format!(":{column}"))));
            loop {
                match self.peek().map(|record| (&record.token, record.emitter)) {
                    Some((Token::Label(slot), Emitter::Model)) => {
                        let label = self.next().expect("the label");
                        let text = self.spell(&Token::Label(*slot), None);
                        atom.push_str(&format!(" {}", self.symbol(label, &text)));
                    }
                    Some((Token::Control(Control::Zero), Emitter::Model)) => {
                        let zero = self.next().expect("0");
                        atom.push_str(&format!(" {}", self.symbol(zero, "0")));
                    }
                    Some((Token::Control(mark @ (Control::Fresh | Control::Key)), Emitter::Model)) => {
                        let shown = self.mark(&column, *mark);
                        atom.push_str(&format!(" {shown}"));
                    }
                    _ => break,
                }
            }
            atom.push(')');
        }
        atom.push(')');
        atom
    }

    /// The names of the columns of the relation `token` names, by position.
    fn relation_columns(&self, token: &Token) -> Vec<String> {
        let typed = |relation: RelationRef| typed_columns(self.registry, &relation).map(|columns| columns.iter().map(|column| column_spelled(&column.name)).collect()).unwrap_or_default();
        match token {
            Token::Fact(fact) => typed(RelationRef::Fact(*fact)),
            Token::Lib(name) | Token::Proposer(name) => typed(RelationRef::Lib(name.clone())),
            Token::Relation(slot) => {
                let declared = self.columns.get(slot).cloned().unwrap_or_default();
                match self.in_form {
                    true => std::iter::once("Example".to_owned()).chain(declared).collect(),
                    false => declared,
                }
            }
            _ => Vec::new(),
        }
    }

    fn instance(&mut self) -> Block {
        let init = self.next().expect("INIT");
        self.in_form = true;
        let name = match self.next() {
            Some(record @ DecodeRecord { token: Token::Lib(name), .. }) => (record, name.clone()),
            _ => return vec![self.symbol(init, "INIT")],
        };
        let component: Option<&Component> = component(self.registry, &name.1);
        let mut items: Vec<Block> = vec![];
        let declared = self.declarations();
        if let Some(component) = component {
            let every: Vec<_> = component.inputs.iter().map(|input| &input.port.name).collect();
            for (slot, port) in declared.iter().zip(component.relation_ports(&every)) {
                self.columns.insert(*slot, port.columns.iter().map(|column| column_spelled(&column.name)).collect());
            }
        }
        if !declared.is_empty() {
            items.push(vec![self.declared_bracket(&declared)]);
        }
        let mut written = Vec::new();
        while let Some(DecodeRecord { token: Token::Column(position), emitter: Emitter::Engine, .. }) = self.peek() {
            self.next();
            let port = (*position as usize).checked_sub(1).and_then(|k| component.and_then(|component| component.inputs.get(k)));
            let label = if *position == 0 { "key".to_owned() } else { port.map_or_else(|| position.to_string(), |port| port.port.name.0.to_string()) };
            if let Some(port) = port {
                written.push(&port.port.name);
            }
            if let Some(skip) = self.take_control(Control::Skip) {
                items.push(vec![format!("[{label}] {}", self.symbol(skip, "SKIP"))]);
                continue;
            }
            items.push(vec![format!("[{label}]")]);
            let body = self.conjuncts(&[Control::End]);
            let mut pieces = body;
            if let Some(end) = self.take_control(Control::End) {
                match pieces.last_mut() {
                    Some(last) => {
                        let line = last.last_mut().expect("a line");
                        *line = format!("{line} {}", self.symbol(end, "END"));
                    }
                    _ => pieces.push(vec![self.symbol(end, "END")]),
                }
            }
            if *position != 0 {
                for column in 0..port.map_or(0, |port| port.port.columns.len()) {
                    let Some(DecodeRecord { token: Token::Column(_), emitter: Emitter::Engine, .. }) = self.peek() else { break };
                    self.next();
                    let column_name = port.map_or_else(String::new, |port| column_spelled(&port.port.columns[column].name));
                    let mut words = Vec::new();
                    while self.peek_control() != Some(Control::End) && self.peek().is_some() {
                        let record = self.next().expect("an answer token");
                        words.push(self.shown(record));
                    }
                    if let Some(end) = self.take_control(Control::End) {
                        words.push(self.symbol(end, "END"));
                    }
                    pieces.push(vec![format!("[{label} {column_name}] ({})", words.join(" "))]);
                }
            }
            items.push(hang("(", pieces, ")"));
        }
        let mut lines = vec![format!("({} {}", self.symbol(init, "INIT"), self.symbol(name.0, &name.1.0))];
        for item in items {
            lines.extend(item.into_iter().map(|line| format!("  {line}")));
        }
        let last = lines.last_mut().expect("a line");
        last.push(')');
        lines
    }
}

/// `blocks` printed after `prefix`, the later blocks and the later lines of
/// the first aligned under the first block, and `close` after the last
/// line.
fn hang(prefix: &str, blocks: Vec<Block>, close: &str) -> Block {
    let pad = " ".repeat(prefix.chars().count());
    let mut lines: Block = Vec::new();
    for line in blocks.into_iter().flatten() {
        lines.push(if lines.is_empty() { format!("{prefix}{line}") } else { format!("{pad}{line}") });
    }
    if lines.is_empty() {
        lines.push(prefix.trim_end().to_owned());
    }
    lines.last_mut().expect("a line").push_str(close);
    lines
}

/// A probability as the trace form writes it: two decimals, with no leading
/// zero.
fn probability_text(probability: f32) -> String {
    let text = format!("{probability:.2}");
    match text.strip_prefix("0.") {
        Some(rest) => format!(".{rest}"),
        None => text.trim_end_matches('0').trim_end_matches('.').to_owned(),
    }
}
