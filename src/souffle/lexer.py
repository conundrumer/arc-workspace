"""The tokens and comments of a Souffle source text, each at its line,
column and offset."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

type TokenKind = Literal["ident", "num", "str", "punct", "hash", "eof"]


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    """The line as numbered after the `#line` directives before it."""
    col: int
    offset: int
    """Where the token starts in the text."""
    phys: int
    """The line's place in the text, counted from 1 whatever `#line`
    directives say."""

    @property
    def end(self) -> int:
        return self.offset + len(self.text)


@dataclass(frozen=True)
class RawComment:
    """A comment as the text writes it, its delimiters included."""

    line: int
    col: int
    text: str
    own_line: bool
    """Nothing but whitespace stands before it on its line."""
    end_line: int
    offset: int
    """Where the comment starts in the text."""


LINE_DIRECTIVE_RE = re.compile(r"#\s*line\s+(\d+)")


class LexError(Exception):
    def __init__(self, line: int, col: int, message: str):
        super().__init__(message)
        self.line = line
        self.col = col
        self.message = message


PUNCT_PAIRS = frozenset({":-", "<=", ">=", "!=", "<:"})
PUNCT_ONE = frozenset("<>=!()[]{},.:;$@|+-*/%^")
SPACE_RE = re.compile(r"[ \t\n\r]+")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _comment_end(text: str, i: int) -> int | None:
    """The end of the comment that starts at `i`; None where none starts
    there, -1 for a block comment that does not end."""
    if text.startswith("//", i):
        j = text.find("\n", i)
        return len(text) if j < 0 else j
    if text.startswith("/*", i):
        j = text.find("*/", i)
        return -1 if j < 0 else j + 2
    return None


def _string_end(text: str, i: int) -> int:
    j, n = i + 1, len(text)
    while j < n and text[j] != '"':
        j += 2 if text[j] == "\\" else 1
    return -1 if j >= n else j + 1


def _hash_end(text: str, i: int) -> int:
    """The end of the `#` line at `i`: the first comment on the line outside
    a string, or the end of the line."""
    at = text.find("\n", i)
    line_end = len(text) if at < 0 else at
    j = i
    while j < line_end:
        if text[j] == '"':
            k = _string_end(text, j)
            if k < 0 or k > line_end:
                return line_end
            j = k
        elif _comment_end(text, j) is not None:
            return j
        else:
            j += 1
    return line_end


def _spans(text: str) -> Iterator[tuple[str, int, int]]:
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\n\r":
            m = SPACE_RE.match(text, i)
            assert m
            kind, end = "space", m.end()
        elif c == "/" and (at := _comment_end(text, i)) is not None:
            kind, end = ("comment", at) if at >= 0 else ("open-comment", n)
        elif c == "#":
            kind, end = "hash", _hash_end(text, i)
        elif c == '"':
            at = _string_end(text, i)
            kind, end = ("str", at) if at >= 0 else ("open-str", n)
        elif m := WORD_RE.match(text, i):
            kind, end = "ident", m.end()
        elif m := NUM_RE.match(text, i):
            kind, end = "num", m.end()
        elif text[i:i + 2] in PUNCT_PAIRS:
            kind, end = "punct", i + 2
        else:
            kind, end = ("punct" if c in PUNCT_ONE else "bad"), i + 1
        yield kind, i, end
        i = end


@lru_cache(maxsize=64)
def lex(text: str) -> tuple[tuple[Token, ...], tuple[RawComment, ...],
                            tuple[tuple[int, int], ...]]:
    """The tokens, ending in one of kind `eof`, and the comments of `text`,
    each at its line as the `#line` directives before it number it; and
    each `#line` directive's renumbering as the text line it starts from
    and the number that line takes. Raises `LexError` for a comment or
    string that does not end and for a character outside the language."""
    tokens: list[Token] = []
    comments: list[RawComment] = []
    renumbered: list[tuple[int, int]] = []
    phys, col = 1, 1
    delta = 0
    for kind, i, end in _spans(text):
        piece = text[i:end]
        line = phys + delta
        if kind == "open-comment":
            raise LexError(line, col, "unterminated block comment")
        if kind == "open-str":
            raise LexError(line, col, "unterminated string")
        if kind == "bad":
            raise LexError(line, col, f"unexpected character {piece!r}")
        breaks = piece.count("\n")
        if kind == "comment":
            start = text.rfind("\n", 0, i) + 1
            comments.append(RawComment(line, col, piece, not text[start:i].strip(),
                                       line + breaks, i))
        elif kind != "space":
            tokens.append(Token(kind, piece, line, col, i, phys))  # type: ignore[arg-type]
        if kind == "hash" and (m := LINE_DIRECTIVE_RE.match(piece)):
            delta = int(m.group(1)) - (phys + 1)
            renumbered.append((phys + 1, int(m.group(1))))
        if breaks:
            phys += breaks
            col = len(piece) - piece.rfind("\n")
        else:
            col += len(piece)
    tokens.append(Token("eof", "", phys + delta, col, len(text), phys))
    return tuple(tokens), tuple(comments), tuple(renumbered)
