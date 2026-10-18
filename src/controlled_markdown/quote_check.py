"""The check of each `quotes` call in code: the handbook document and the
heading it names stand, and its words stand under that heading
(`check_quotes`), with the text of each section of a handbook document
that the check compares (`handbook_sections`)."""

from __future__ import annotations

import ast
import functools
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from engine import checkout
from engine.quotes import quotes

from controlled_markdown import (
    ControlledMarkdownError,
    HEADING,
    Node,
    parse,
    Rule,
    section_lines,
)


# A `quotes` call names a handbook document, a heading in it and the words
# under that heading. The checker's own rule on which of its functions have
# one is `checker.quoting`'s.
LINE_MARKER_RE = re.compile(r"^\s*(?:[-+*]\s+|\d+\.\s+)?")


@dataclass(frozen=True)
class Quote:
    """One `quotes(document, heading, words)` call, read as a literal."""
    line: int
    document: str
    heading: str
    words: str


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _quote(node: ast.Call, source: str) -> Quote:
    """The three strings of a `quotes` call, which the check reads without
    running the program."""
    names = ("document", "heading", "words")
    given = dict(zip(names, node.args))
    given.update((k.arg, k.value) for k in node.keywords if k.arg in names)
    values = [v.value for name in names
              if isinstance(v := given.get(name), ast.Constant)
              and isinstance(v.value, str)]
    if len(values) != 3 or len(node.args) + len(node.keywords) != 3:
        raise ControlledMarkdownError(
            source, node.lineno, Rule.QUOTE_LITERAL,
            "a `quotes` call takes three string literals: the document, the "
            "heading and the words")
    return Quote(node.lineno, *values)


def _squeezed(text: str) -> str:
    return " ".join(text.split())


def _headings(node: Node) -> Iterator[Node]:
    """The headings under `node`, in document order."""
    for child in node.children:
        if child.kind == HEADING:
            yield child
            yield from _headings(child)


@functools.cache
def handbook_sections(document: Path) -> dict[str, list[str]]:
    """Each heading's text, as `parse` reads it, mapped to the text that
    stands under it, its subsections included, as one line per heading of
    that text: its `section_lines` after the heading's line, each with its
    marker and indent dropped."""
    text = document.read_text()
    lines = text.splitlines(keepends=True)
    tree = parse(text, str(document))
    out: dict[str, list[str]] = {}
    for heading in _headings(tree):
        body = (LINE_MARKER_RE.sub("", ln, count=1)
                for ln in section_lines(tree, heading, lines)[1:])
        out.setdefault(heading.text, []).append(_squeezed(" ".join(body)))
    return out


def check_quotes(path: Path, source: str) -> list[ControlledMarkdownError]:
    """Every `quotes` call names a handbook document and a heading in it,
    and its words stand under that heading, up to line wrapping."""
    text = path.read_text()
    if quotes.__name__ not in text:
        return []
    tree = ast.parse(text, str(path))
    errors: list[ControlledMarkdownError] = []
    found: list[Quote] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == quotes.__name__:
            try:
                found.append(_quote(node, source))
            except ControlledMarkdownError as err:
                errors.append(err)
    for q in found:
        document = checkout.handbook() / q.document
        if not document.is_file():
            errors.append(ControlledMarkdownError(
                source, q.line, Rule.QUOTE_DOCUMENT,
                f"no handbook document `{q.document}`"))
            continue
        under = handbook_sections(document).get(q.heading)
        if under is None:
            errors.append(ControlledMarkdownError(
                source, q.line, Rule.QUOTE_HEADING,
                f"no heading \"{q.heading}\" in `{q.document}`"))
        elif not any(_squeezed(q.words) in body for body in under):
            errors.append(ControlledMarkdownError(
                source, q.line, Rule.QUOTE_WORDS,
                f"not under \"{q.heading}\" in `{q.document}`: "
                f"\"{_squeezed(q.words)}\""))
    return errors
