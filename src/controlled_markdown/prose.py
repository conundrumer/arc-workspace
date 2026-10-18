"""The checks of prose in code: each string a program marks with `mctx`,
each doc comment of the lib, each `quotes` call and each path a code file
names; with `mctx` itself, and `form`, the pattern that reads back a text
built from an `mctx` template. It holds as well the check of the words of
any prose, in a document or in code."""

from __future__ import annotations

import ast
import functools
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from engine import checkout
from engine.quotes import quotes

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
from controlled_markdown.nodes import slug
from controlled_markdown.renderers import markdown_heading_lines


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
                yield ControlledMarkdownError(
                    node.source, node.line + at, Rule.LITERAL_WORD,
                    f"{', '.join(f'`{w}`' for w in words)}: a line says the "
                    f"relation it means with a literal verb, such as `has`, "
                    f"`gives`, `holds`, `does` or `takes`")


def code_carry_errors(path: Path, source: str) -> Iterator[ControlledMarkdownError]:
    """A finding at each line of a fragment or of a lib doc comment that the
    file `path` holds whose own words hold a form of `carry`, at its line in
    the file. Where the other rules refuse to read a fragment, or the file's
    fragments past one, this check reads neither: those rules report it."""
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
            yield node.lineno, dedent(node.value)
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
        yield Fragment(dedent("".join(body)), path, source, line)


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
    """Every fragment a file holds, checked where it stands. An error carries
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


# A path a document takes in the repo: the shapes the document set uses, so a
# literal that names one is checked against the tree.
DOC_PATH_RE = re.compile(
    r"^(?:docs/[\w./-]+\.md|prompts/[\w./-]+\.md|CLAUDE\.md"
    r"|\.claude/[\w./-]+\.md)$")


def _named_paths(path: Path, text: str):
    """Every string a file holds that names a document, with its line. A
    string holding a hole or a wildcard names a shape and is passed over."""
    def wanted(value: str, line: int):
        if "{" in value or "*" in value or not DOC_PATH_RE.match(value):
            return
        yield line, value

    if path.suffix == ".py":
        for node in ast.walk(ast.parse(text, str(path))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield from wanted(node.value, node.lineno)
        return
    for m in JS_STRING_RE.finditer(text):
        yield from wanted(m.group(2), text.count("\n", 0, m.start()) + 1)


JS_STRING_RE = re.compile(r"""(['"])((?:[^'"\\\n]|\\.)*?)\1""")


def check_paths(path: Path, source: str, root: Path) -> None:
    """Every document a file names by path stands in the tree. A name that
    goes stale is a reference no reader can follow."""
    for line, value in _named_paths(path, path.read_text()):
        if not (root / value).exists():
            raise ControlledMarkdownError(
                source, line, Rule.PATH_MISSING,
                f"no file at `{value}`")


# A citation in code: a document by its path from the root of the tree, and
# a section of it by the slug of its heading.
CITATION_RE = re.compile(r"(?:docs|work)/[\w./-]+\.md(?:#[\w-]+)?")


def _citations(path: Path) -> Iterator[tuple[int, str, str, str]]:
    """Every citation the file holds, with its line, its path and its
    anchor, empty where it has none. A file that is no UTF-8 text holds
    none."""
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        return
    for at, line in enumerate(text.split("\n"), 1):
        for m in CITATION_RE.finditer(line):
            name, _, anchor = m.group(0).partition("#")
            yield at, m.group(0), name, anchor


def _anchor_fault(source: str, at: int, citation: str, name: str,
                  anchor: str, root: Path) -> ControlledMarkdownError | None:
    """The fault of an anchor that names no heading of the cited file. The
    headings are read from the file's text, since a cited spec file stands
    outside the document set."""
    if anchor in {slug(heading) for _, _, heading in
                  markdown_heading_lines((root / name).read_text())}:
        return None
    return ControlledMarkdownError(source, at, Rule.CITATION_ANCHOR,
                                   f"`{citation}` names no heading of `{name}`")


def check_citations(path: Path, source: str, root: Path,
                    present: frozenset[str]) -> Iterator[ControlledMarkdownError]:
    """Every citation a file of the engine holds names a file of `present`,
    the files a commit of the tree takes, and its anchor, where it has one,
    a heading of that file. A citation of a file a clone does not hold is
    one no reader of the code can follow."""
    for at, citation, name, anchor in _citations(path):
        if name not in present:
            yield ControlledMarkdownError(
                source, at, Rule.PATH_MISSING,
                f"`{citation}` names no file a commit of the tree takes")
        elif anchor and (err := _anchor_fault(source, at, citation, name,
                                               anchor, root)):
            yield err


def check_citation_anchors(path: Path, source: str,
                           root: Path) -> Iterator[ControlledMarkdownError]:
    """Every anchor of a citation the file holds names a heading of the
    cited file, where the tree holds that file. Code outside the engine
    names untracked files by path on purpose, so a cited file that is
    absent is passed over."""
    for at, citation, name, anchor in _citations(path):
        if anchor and (root / name).is_file() and (
                err := _anchor_fault(source, at, citation, name, anchor, root)):
            yield err


# A `quotes` call names a handbook document, a heading in it and the words
# under that heading. The checker's own rule on which of its functions carry
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
    that text with each line's marker and indent dropped."""
    text = document.read_text()
    lines = text.split("\n")
    heads = [(h.line - 1, h.depth, h.text)
             for h in _headings(parse(text, str(document)))]
    out: dict[str, list[str]] = {}
    for k, (i, depth, title) in enumerate(heads):
        end = next((j for j, d, _ in heads[k + 1:] if d <= depth),
                   len(lines))
        body = (LINE_MARKER_RE.sub("", ln, count=1) for ln in lines[i + 1:end])
        out.setdefault(title, []).append(_squeezed(" ".join(body)))
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


# The lib's doc comments: `//!` heads a file's doc and `///` an item's. Each
# line is the text of one statement, so it takes the rules on a statement's
# text and neither the marker nor the indent rules.
DL_DOC_RE = re.compile(r"^\s*(?://!|///)[ \t]?(.*)$")


def dl_fragments(path: Path, source: str):
    """Every doc-comment line a Souffle file holds. A line blank after its
    marker carries no prose."""
    for n, line in enumerate(path.read_text().split("\n"), 1):
        m = DL_DOC_RE.match(line)
        if m is not None and m.group(1).strip():
            yield Fragment(m.group(1).strip(), path, source, n)


def check_dl_comments(path: Path, source: str, root: Path | None = None):
    """Every doc-comment line, read as the text of one statement."""
    for fragment in dl_fragments(path, source):
        check_links(_statement(fragment.text, source, fragment.line), path,
                    root)
