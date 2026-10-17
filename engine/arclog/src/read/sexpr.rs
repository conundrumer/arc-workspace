//! The fixed s-expression reader: lists, symbols, quoted strings and `;`
//! comments. A string escapes `"` and `\` with a `\`, and holds no other
//! escape.

use crate::diagnostic::Diagnostic;
use crate::layout::{Comment, SourceFile, SourcePlace};

use super::{grammar, SExpr};

/// A position in the text: its byte offset, and its line and column, both
/// counted from 1, the column in characters.
#[derive(Clone, Copy)]
struct Position {
    byte: usize,
    line: u32,
    column: u32,
}

struct Scanner<'a> {
    text: &'a str,
    file: SourceFile,
    at: Position,
}

impl Scanner<'_> {
    fn peek(&self) -> Option<char> {
        self.text[self.at.byte..].chars().next()
    }

    fn bump(&mut self) -> Option<char> {
        let c = self.peek()?;
        self.at.byte += c.len_utf8();
        if c == '\n' {
            self.at.line += 1;
            self.at.column = 1;
        } else {
            self.at.column += 1;
        }
        Some(c)
    }

    fn place(&self, start: Position) -> SourcePlace {
        SourcePlace {
            file: self.file,
            start: start.byte as u32,
            end: self.at.byte as u32,
            line: start.line,
            column: start.column,
        }
    }
}

fn ends_symbol(c: char) -> bool {
    c.is_whitespace() || matches!(c, '(' | ')' | '"' | ';')
}

/// A list being read: its items so far and the place of its `(`.
struct Open {
    items: Vec<SExpr>,
    start: Position,
}

pub(super) fn read(text: &str, file: SourceFile) -> Result<(Vec<SExpr>, Vec<Comment>), Vec<Diagnostic>> {
    let mut scanner = Scanner { text, file, at: Position { byte: 0, line: 1, column: 1 } };
    let mut top: Vec<SExpr> = Vec::new();
    let mut open: Vec<Open> = Vec::new();
    let mut comments = Vec::new();
    let mut diagnostics = Vec::new();
    while let Some(c) = scanner.peek() {
        let start = scanner.at;
        let item = match c {
            c if c.is_whitespace() => {
                scanner.bump();
                continue;
            }
            ';' => {
                while scanner.peek().is_some_and(|c| c != '\n') {
                    scanner.bump();
                }
                let place = scanner.place(start);
                comments.push(Comment { place, text: text[start.byte..scanner.at.byte].into() });
                continue;
            }
            '(' => {
                scanner.bump();
                open.push(Open { items: Vec::new(), start });
                continue;
            }
            ')' => {
                scanner.bump();
                let close = scanner.place(start);
                let Some(list) = open.pop() else {
                    diagnostics.push(grammar("a `)` closes no list", close));
                    continue;
                };
                let mut place = scanner.place(list.start);
                place.end = close.end;
                SExpr::List { items: list.items.into(), place, close }
            }
            '"' => {
                scanner.bump();
                let mut content = String::new();
                let mut closed = false;
                while let Some(c) = scanner.bump() {
                    match c {
                        '"' => {
                            closed = true;
                            break;
                        }
                        '\\' => {
                            let escape = scanner.at;
                            match scanner.bump() {
                                Some(e @ ('"' | '\\')) => content.push(e),
                                _ => diagnostics.push(grammar(
                                    "a string escapes only `\"` and `\\`",
                                    scanner.place(escape),
                                )),
                            }
                        }
                        c => content.push(c),
                    }
                }
                let place = scanner.place(start);
                if !closed {
                    diagnostics.push(grammar("the string is not terminated", place));
                    break;
                }
                SExpr::String { text: content.into(), place }
            }
            _ => {
                while scanner.peek().is_some_and(|c| !ends_symbol(c)) {
                    scanner.bump();
                }
                let place = scanner.place(start);
                SExpr::Symbol { text: text[start.byte..scanner.at.byte].into(), place }
            }
        };
        match open.last_mut() {
            Some(list) => list.items.push(item),
            None => top.push(item),
        }
    }
    for list in open {
        let at = Scanner { text, file, at: list.start };
        let mut place = at.place(list.start);
        place.end = list.start.byte as u32 + 1;
        diagnostics.push(grammar("the list is not closed", place));
    }
    if diagnostics.is_empty() { Ok((top, comments)) } else { Err(diagnostics) }
}
