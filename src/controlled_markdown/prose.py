"""The checks of prose in code: each string a program marks with `mctx`
and each doc comment of the lib; with `mctx` itself, and
`form`, the pattern that reads back a text built from an `mctx` template.
It holds as well the check of the words of any prose, in a document or in
code, and the reader of the docstrings and comments of Python code."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from engine import checkout

from controlled_markdown import (
    check_order,
    CONTENT,
    ControlledMarkdownError,
    DOCUMENT,
    HEADING,
    Node,
    parse,
    Rule,
    TABLE,
)
from controlled_markdown.document_set import carried, check_blocks, check_links


# ----------------------------------------------------------------- prose

def mctx(prose):
    """A string a program holds that enters an agent's context. On a str it
    strips the common indent and the blank lines around it; on a dict it
    returns the dict as it stands, each value being a fragment of its own.

    The name is the marker the check reads: every `mctx` call in the repo
    gives up its strings, and each is checked as the format."""
    if isinstance(prose, str):
        return dedent(prose)
    return prose


def form(template: str, holes: dict[str, str]) -> str:
    """The pattern of the text `template` gives, with each hole of `holes`
    matched by its pattern."""
    pattern = re.escape(template)
    for hole, matched in holes.items():
        pattern = pattern.replace(re.escape("{" + hole + "}"), matched)
    return pattern


def dedent(text: str) -> str:
    """Text with the indent its lines share taken off and its outer blank
    lines dropped."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    pad = min((len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()),
              default=0)
    return "\n".join(ln[pad:] if ln.strip() else "" for ln in lines)


def dropped_lines(text: str) -> int:
    """The count of blank lines at the start of `text`, which `dedent` drops."""
    return text[:len(text) - len(text.lstrip())].count("\n")


# ----------------------------------------------------------------- words

# Each form of `carry`, which this tree uses only in a figurative sense. The
# rule on literal words of `docs/handbook/editing.md#writing-a-file` has the
# check report each one; other words of that rule have literal uses of the
# same form, so no check of their form tells the two apart.
CARRY_RE = re.compile(r"\b(?:carry|carries|carrying|carried)\b", re.IGNORECASE)
# What a line holds that is not its own words: a code span, and words in
# quotes.
NOT_OWN_RE = re.compile(r'(`+).*?\1|"[^"]*"|\u201c[^\u201d]*\u201d')


def carry_words(text: str) -> list[str]:
    """Each form of `carry` in `text`, outside its code spans and the words
    it quotes."""
    return CARRY_RE.findall(NOT_OWN_RE.sub(" ", text))


def carry_errors(document: Node) -> Iterator[ControlledMarkdownError]:
    """A finding at each line of `document` that a render shows and whose
    own words hold a form of `carry`. A code block, a quote and an attribute
    hold no words of the line's own."""
    for node in carried(document):
        if node.kind not in (CONTENT, HEADING, TABLE):
            continue
        for at, line in enumerate(node.text.split("\n")):
            if words := carry_words(line):
                yield _carry_error(node.source, node.line + at, words)


def _carry_error(source: str, line: int,
                 words: list[str]) -> ControlledMarkdownError:
    """The finding at `line` of `source`, whose own words hold `words`."""
    return ControlledMarkdownError(
        source, line, Rule.LITERAL_WORD,
        f"{', '.join(f'`{w}`' for w in words)}: a line says the relation it "
        f"means with a literal verb, such as `has`, `gives`, `holds`, `does` "
        f"or `takes`")


# The deprecated console, whose docstrings and comments `code_prose_lines`
# passes over.
DEPRECATED = checkout.console()


def code_prose_lines(path: Path) -> list[tuple[int, str]]:
    """Each line of a docstring or of a comment of the Python file `path`,
    with its line, as `python_prose_lines` gives them; none where `path` is
    no Python file or stands in `DEPRECATED`."""
    if path.suffix != ".py" or path.resolve().is_relative_to(DEPRECATED):
        return []
    return python_prose_lines(path.read_text())


def code_carry_errors(path: Path, source: str) -> Iterator[ControlledMarkdownError]:
    """A finding at each line of a fragment, of a lib doc comment, or of a
    docstring or a comment of a Python file outside `DEPRECATED`, that the
    file `path` holds and whose own words hold a form of `carry`, at its
    line in the file. Where the other rules refuse to read a fragment, or
    the file's fragments past one, this check reads neither: those rules
    report it. The docstrings and comments are read apart from the
    fragments."""
    for line, text in code_prose_lines(path):
        if words := carry_words(text):
            yield _carry_error(source, line, words)
    if path.suffix == ".dl":
        for fragment in dl_fragments(path, source):
            yield from carry_errors(_statement(fragment.text, source,
                                               fragment.line))
        return
    try:
        for fragment in fragments(path, source):
            try:
                document, _ = _fragment_document(fragment)
            except ControlledMarkdownError:
                continue
            for err in carry_errors(document):
                yield _at_file_line(fragment, err)
    except ControlledMarkdownError:
        return


# The prefix and the opening quotes of a Python string literal.
STRING_OPEN_RE = re.compile(r"^[A-Za-z]*(\"\"\"|'''|\"|')")


def python_prose_lines(text: str) -> list[tuple[int, str]]:
    """Each line of a docstring or of a `#` comment of the Python text
    `text`, with its line, in the order of the lines. A docstring is any bare
    string statement, wherever it stands, read as its source spells each of
    its literals, so each line is the file's own line; a comment gives its
    text after the `#`. A text that does not parse gives none."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    bare = [((n.lineno, n.col_offset), (n.end_lineno, n.end_col_offset))
            for n in ast.walk(tree)
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)]
    lines: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            lines.append((token.start[0], token.string[1:]))
        elif token.type == tokenize.STRING and any(
                start <= token.start and token.end <= end
                for start, end in bare):
            opening = STRING_OPEN_RE.match(token.string)
            assert opening is not None, token.string
            body = token.string[opening.end():-len(opening.group(1))]
            lines.extend((token.start[0] + at, ln)
                         for at, ln in enumerate(body.split("\n")))
    return sorted(lines)


# A hole a fragment leaves for the program to fill: `{name}` in Python,
# `${name}` in JavaScript. The check puts one opaque word in its place, since
# what stands there is a value and not prose.
PY_HOLE_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}")
JS_HOLE_RE = re.compile(r"\$\{([^}]*)\}")
HOLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
FILLED = "value"


@dataclass
class Fragment:
    """One string a program holds, with where it stands."""
    text: str
    file: Path
    source: str
    line: int


def _py_fragments(tree, path: Path, source: str):
    """Every string an `mctx` call in a Python file gives up. A call whose
    argument is not a literal is an error: the prose is read without running
    the program."""
    def values(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno + dropped_lines(node.value), dedent(node.value)
        elif isinstance(node, ast.Dict):
            for v in node.values:
                yield from values(v)
        else:
            raise ControlledMarkdownError(
                source, node.lineno, Rule.MCTX_LITERAL,
                "`mctx` takes a string or a dict of them, written out")

    def tagged(func) -> bool:
        """The call is `mctx`, by its own name or through a module."""
        if isinstance(func, ast.Name):
            return func.id == "mctx"
        return isinstance(func, ast.Attribute) and func.attr == "mctx"

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and tagged(node.func)
                and len(node.args) == 1):
            for line, text in values(node.args[0]):
                yield Fragment(text, path, source, line)


# The tag, where it opens a literal: a name on its own, and not the word in
# a comment or inside a span.
JS_TAG_RE = re.compile(r"(?<![A-Za-z0-9_$`])mctx`")

def _js_fragments(text: str, path: Path, source: str):
    """Every string an `mctx` tag in a JavaScript file gives up. A backtick
    inside the literal opens a nested one, which the check does not read."""
    for m in JS_TAG_RE.finditer(text):
        at = m.start()
        line = text.count("\n", 0, at) + 1
        j, depth, body = m.end(), 0, []
        while j < len(text):
            ch = text[j]
            if ch == "\\" and j + 1 < len(text):
                body.append(text[j + 1])
                j += 2
                continue
            if ch == "$" and text[j:j + 2] == "${":
                depth += 1
            elif ch == "}" and depth:
                depth -= 1
            elif ch == "`":
                if depth:
                    raise ControlledMarkdownError(
                        source, line + "".join(body).count("\n"), Rule.MCTX_NESTED,
                        "a backtick inside an `mctx` literal opens a nested "
                        "one")
                break
            body.append(ch)
            j += 1
        literal = "".join(body)
        yield Fragment(dedent(literal), path, source,
                       line + dropped_lines(literal))


PY_WHOLE_RE = re.compile(r"^\s*\{[A-Za-z_][A-Za-z0-9_.]*\}\s*$")
JS_WHOLE_RE = re.compile(r"^\s*\$\{[^}]*\}\s*$")


def _placed(text: str, whole: re.Pattern) -> str:
    """A line that is one hole places a fragment of its own, checked where
    that fragment stands, so this one reads past it."""
    return "\n".join("" if whole.match(ln) else ln for ln in text.split("\n"))


def _holed(fragment: Fragment) -> str:
    """The fragment with each hole replaced by one opaque word, so what the
    program fills is read as a value and not as prose. A line that is one
    hole is left blank: it places a fragment the check reads on its own."""
    if fragment.file.suffix == ".py":
        def py_hole(m):
            if m.group(1) is None:
                return m.group(0)[0]
            return FILLED
        return PY_HOLE_RE.sub(py_hole, _placed(fragment.text, PY_WHOLE_RE))

    def js_hole(m):
        if not HOLE_NAME_RE.match(m.group(1).strip()):
            raise ControlledMarkdownError(
                fragment.source, fragment.line, Rule.HOLE_NAME,
                f"`${{{m.group(1)}}}` is not a name; a fragment leaves a hole "
                f"for a value the program computes above it")
        return FILLED
    return JS_HOLE_RE.sub(js_hole, _placed(fragment.text, JS_WHOLE_RE))


MARKER_RE = re.compile(r"^(?:[-+*>|]\s|\d+\.\s|#{1,6}\s|`{3,}|~{3,})")


def _statement(text: str, source: str, line: int) -> Node:
    """A document of one statement, `text`, at `line`."""
    document = Node(DOCUMENT, source=source)
    document.children = [Node(CONTENT, text=text, source=source, line=line)]
    return document


def _fragment_document(fragment: Fragment) -> tuple[Node, bool]:
    """The fragment as a document, and whether it is format lines: a
    fragment that opens with a marker is, and any other fragment is the text
    of one statement."""
    text = _holed(fragment)
    opening = next((ln for ln in text.split("\n") if ln.strip()), "")
    if MARKER_RE.match(opening):
        # A fragment is a run of lines, not a document: the brief that places
        # it supplies the line a block stands under.
        return parse(text, fragment.source, fragment=True), True
    if "\n" in text:
        raise ControlledMarkdownError(
            fragment.source, 1, Rule.FRAGMENT_BREAK,
            "a fragment that is one statement holds one line")
    return _statement(text, fragment.source, 1), False


def check_fragment(fragment: Fragment, root: Path | None = None) -> None:
    """One fragment under the rules its shape takes: format lines take every
    rule, and the text of one statement takes the text rules."""
    document, lines = _fragment_document(fragment)
    if lines:
        check_order(document)
        check_blocks(document)
    check_links(document, fragment.file, root)


def fragments(path: Path, source: str):
    """Every fragment a file holds."""
    yield from text_fragments(path.read_text(), path, source)


def text_fragments(text: str, path: Path, source: str):
    """Every fragment the text `text` of the file `path` holds, which may
    be the file's text at another commit than the tree's."""
    if path.suffix == ".py":
        if "mctx" not in text:
            return
        yield from _py_fragments(ast.parse(text, str(path)), path, source)
    elif "mctx`" in text:
        yield from _js_fragments(text, path, source)


def check_file_fragments(path: Path, source: str,
                         root: Path | None = None) -> None:
    """Every fragment a file holds, checked where it stands. An error gives
    the file and the fragment's own line, offset within a multi-line one."""
    for fragment in fragments(path, source):
        try:
            check_fragment(fragment, root)
        except ControlledMarkdownError as err:
            raise _at_file_line(fragment, err) from None


def _at_file_line(fragment: Fragment,
                  err: ControlledMarkdownError) -> ControlledMarkdownError:
    """The error `err` of a line of `fragment`, at that line in the file."""
    return ControlledMarkdownError(
        fragment.source, fragment.line + max(err.line - 1, 0), err.rule,
        err.message)


# The lib's doc comments: `//!` heads a file's doc and `///` an item's. Each
# line is the text of one statement, so it takes the rules on a statement's
# text and neither the marker nor the indent rules.
DL_DOC_RE = re.compile(r"^\s*(?://!|///)[ \t]?(.*)$")


def dl_fragments(path: Path, source: str):
    """Every doc-comment line a Souffle file holds. A line blank after its
    marker holds no prose."""
    for n, line in enumerate(path.read_text().split("\n"), 1):
        m = DL_DOC_RE.match(line)
        if m is not None and m.group(1).strip():
            yield Fragment(m.group(1).strip(), path, source, n)


def check_dl_comments(path: Path, source: str, root: Path | None = None):
    """Every doc-comment line, read as the text of one statement."""
    for fragment in dl_fragments(path, source):
        check_links(_statement(fragment.text, source, fragment.line), path,
                    root)
