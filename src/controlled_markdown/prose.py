"""The checks of prose in code: each string a program marks with `mctx`,
each doc comment of the lib, each `quotes` call and each path a code file
names, and the checks of a document set: its links, its blocks, its
closure and its partials."""

from __future__ import annotations

import ast
import functools
import inspect
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from engine import checkout
from engine.quotes import quotes

from controlled_markdown import (
    check_order,
    CODE,
    COMMENT,
    CONTENT,
    ControlledMarkdownError,
    DOCUMENT,
    HEADING,
    INCLUDE,
    INLINE,
    Node,
    parse,
    QUOTE,
    Registry,
    slug,
    TABLE,
    _walk,
)


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
                source, node.lineno, "mctx-literal",
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
                        source, line + "".join(body).count("\n"), "mctx-nested",
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
                fragment.source, fragment.line, "hole-name",
                f"`${{{m.group(1)}}}` is not a name; a fragment leaves a hole "
                f"for a value the program computes above it")
        return FILLED
    return JS_HOLE_RE.sub(js_hole, _placed(fragment.text, JS_WHOLE_RE))


MARKER_RE = re.compile(r"^(?:[-+*>|]\s|\d+\.\s|#{1,6}\s|`{3,}|~{3,})")


def check_fragment(fragment: Fragment, root: Path | None = None) -> None:
    """One fragment under the rules its shape takes. A fragment that opens
    with a marker is format lines and takes every rule; any other fragment is
    the text of one statement and takes the text rules."""
    text = _holed(fragment)
    opening = next((ln for ln in text.split("\n") if ln.strip()), "")
    if MARKER_RE.match(opening):
        # A fragment is a run of lines, not a document: the brief that places
        # it supplies the line a block stands under.
        document = parse(text, fragment.source, fragment=True)
        check_order(document)
        check_blocks(document)
        check_links(document, fragment.file, root)
        return
    if "\n" in text:
        raise ControlledMarkdownError(
            fragment.source, 1, "fragment-break",
            "a fragment that is one statement holds one line")
    node = Node(CONTENT, text=text, source=fragment.source, line=1)
    document = Node(DOCUMENT, source=fragment.source)
    document.children = [node]
    check_links(document, fragment.file, root)


def fragments(path: Path, source: str):
    """Every fragment a file holds."""
    text = path.read_text()
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
            raise ControlledMarkdownError(
                source, fragment.line + max(err.line - 1, 0), err.rule,
                err.message) from None


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
                source, line, "path-missing",
                f"no file at `{value}`")


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
            source, node.lineno, "quote-literal",
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
                source, q.line, "quote-document",
                f"no handbook document `{q.document}`"))
            continue
        under = handbook_sections(document).get(q.heading)
        if under is None:
            errors.append(ControlledMarkdownError(
                source, q.line, "quote-heading",
                f"no heading \"{q.heading}\" in `{q.document}`"))
        elif not any(_squeezed(q.words) in body for body in under):
            errors.append(ControlledMarkdownError(
                source, q.line, "quote-words",
                f"not under \"{q.heading}\" in `{q.document}`: "
                f"\"{_squeezed(q.words)}\""))
    return errors


def check_quote_rule(shown: Callable[[Path], str]
                     ) -> list[ControlledMarkdownError]:
    """Each check or survey of the checker that breaks its rule on the words
    it rests on (`checker.quoting`), at its `def` line, its file as `shown`
    gives it."""
    from checker.quoting import (PRINCIPLES, Breach, checks_and_surveys,
                                 unquoted)
    sentence = {
        Breach.GUARD: "`{name}` carries a `guard`, which only a hint or lint "
                      "check may carry",
        Breach.MISSING: "`{name}` carries no `quotes`",
        Breach.PRINCIPLE: "`{name}` carries no `quotes` from `{principles}`",
    }
    errors: list[ControlledMarkdownError] = []
    for u in unquoted(checks_and_surveys()):
        lines, first = inspect.getsourcelines(u.function)
        at = first + next(i for i, ln in enumerate(lines)
                          if ln.lstrip().startswith(("def ", "async def ")))
        errors.append(ControlledMarkdownError(
            shown(Path(inspect.getfile(u.function))), at, u.breach.value,
            sentence[u.breach].format(name=u.function.__name__,
                                      principles=PRINCIPLES)))
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
        node = Node(CONTENT, text=fragment.text, source=source,
                    line=fragment.line)
        document = Node(DOCUMENT, source=source)
        document.children = [node]
        check_links(document, path, root)


def reached(entry: Path, registry: Registry) -> set[str]:
    """Every document the composition at `entry` reaches, by source name: the
    entry, what it includes, and what those include, down."""
    out: set[str] = set()

    def walk(path: Path) -> None:
        try:
            document = registry.open(path)
        except OSError:
            return
        if document.source in out:
            return
        out.add(document.source)
        for node in _walk(document):
            for name in (INCLUDE, INLINE):
                if not node.has(name):
                    continue
                where = (node.attr(name) or "").strip().partition("#")[0]
                if where:
                    walk(path.parent / where)

    walk(entry)
    return out


def carried(node: Node) -> Iterator[Node]:
    """Every node a render carries: the lines under a `comment` are the
    editor's and reach no reader."""
    for child in node.children:
        if child.has(COMMENT):
            continue
        yield child
        yield from carried(child)


def check_closure(entries: list[Path], document_set: set[Path],
                  root: Path) -> None:
    """A document a composition includes links only to another document in
    that set, or to a file outside the document set. A link to a document the
    render leaves out sends its reader where the render does not go.

    An entry document is the composition itself, and its lead is its own: it
    points an editor at what the render leaves out, so it is not closed. Only
    the lines a render carries count, so a link under a `comment` is the
    editor's and not a reader's.
    """
    registry = Registry(root)
    opened = {registry.rel(registry.open(e)) for e in entries}
    inside: set[str] = set()
    for entry in entries:
        inside |= reached(entry, registry)
    for source in sorted(inside - opened):
        document = registry.documents[source]
        file = registry.sources[source]
        for node in carried(document):
            if node.kind == CODE or not node.text:
                continue
            for _, _, path, _ in _text_links(node):
                if not path:
                    continue
                target = target_of(path, file, root)
                if target not in document_set:
                    continue
                if registry.rel(registry.open(target)) not in inside:
                    raise ControlledMarkdownError(
                        source, node.line, "handbook-link",
                        f"`{path}` is a document the handbook does not carry")


# The heading whose sections are the partials of a document: the runs of
# lines the document's own messages inline.
PARTIALS = "Partials"


def partials(document: Node) -> list[Node]:
    """The sections under a `Partials` heading of `document`: the headings one
    level under it. A heading deeper than that belongs to a partial's body."""
    out: list[Node] = []
    for node in _walk(document):
        if node.kind == HEADING and node.text == PARTIALS:
            out.extend(c for c in node.children if c.kind == HEADING)
    return out


def inline_sites(documents: list[tuple[Path, Node]]) -> dict[tuple[Path, str], int]:
    """How many `inline` directives reach each section, keyed by the target
    document's resolved path and the id the directive names. A directive with
    no path before the `#` reaches its own document."""
    out: dict[tuple[Path, str], int] = {}
    for file, document in documents:
        for node in _walk(document):
            value = node.attr(INLINE)
            if value is None:
                continue
            where, hashed, ident = value.strip().partition("#")
            where, ident = where.strip(), ident.strip()
            if not hashed or not ident:
                continue
            target = (file.parent / where).resolve() if where else file
            out[(target, ident)] = out.get((target, ident), 0) + 1
    return out


# How many sites a partial is inlined at. A run of lines one site uses belongs
# at that site.
PARTIAL_SITES = 2


def check_partial_sites(
        documents: list[tuple[Path, Node]]) -> list[ControlledMarkdownError]:
    """Each partial is inlined at `PARTIAL_SITES` sites at least, counted over
    the whole document set. Each file is given as its resolved path and its
    parsed document, and the errors come back one per partial."""
    sites = inline_sites(documents)
    out: list[ControlledMarkdownError] = []
    for file, document in documents:
        for heading in partials(document):
            ident = slug(heading.text)
            count = sites.get((file.resolve(), ident), 0)
            if count < PARTIAL_SITES:
                out.append(ControlledMarkdownError(
                    heading.source, heading.line, "partial-sites",
                    f"`{ident}` is a partial inlined at {count} "
                    f"{'site' if count == 1 else 'sites'}; a partial is "
                    f"inlined at two sites at least"))
    return out


def check_blocks(node: Node) -> None:
    """A line has at most one block under it, a block being a code node, a
    quote, or a table. Two quotes a blank line apart are two blocks. The
    formatter does not settle this, so a document is checked for it."""
    seen = False
    for child in node.children:
        if child.kind in (CODE, QUOTE, TABLE):
            if seen:
                raise ControlledMarkdownError(child.source, child.line,
                                          "block-repeat",
                                          "a line carries one code node, "
                                          "quote, or table at most")
            seen = True
        check_blocks(child)


LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
SPAN_RE = re.compile(r"(`[^`]*`)")
SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:|^//|^#")


def _text_links(node: Node) -> Iterator[tuple[Node, str, str, str]]:
    """Every link in one node's text, as (node, text, path, slug). A backtick
    span is literal, so a link written inside one is text."""
    for part in SPAN_RE.split(node.text):
        if part.startswith("`"):
            continue
        for m in LINK_RE.finditer(part):
            target = m.group(2)
            if SCHEME_RE.match(target):
                continue
            path, _, slug = target.partition("#")
            yield node, m.group(1), path, slug


def links(node: Node) -> Iterator[tuple[Node, str, str, str]]:
    """Every link under `node`."""
    for child in _walk(node):
        if child.kind == CODE or not child.text:
            continue
        yield from _text_links(child)


def target_of(path: str, file: Path, root: Path | None = None) -> Path:
    """Where a link's target stands. A target that opens with `./` or `../`
    is relative to the document that holds it; every other target is relative
    to the repo root, since that is where a session runs."""
    if not path:
        return file.resolve()
    base = file.parent if path.startswith(("./", "../")) else (root or Path.cwd())
    return (base / path).resolve()


def check_links(document: Node, file: Path, root: Path | None = None) -> None:
    """Every link in the document resolves: the file or directory stands where
    `target_of` puts it, and a slug names a heading of that file whose text the
    link text gives. An external target is skipped."""
    for node, text, path, ident in links(document):
        target = target_of(path, file, root)
        if not target.exists():
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"nothing at `{path}`")
        if not ident:
            continue
        if not target.is_file():
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"`{path}` is a directory and holds no "
                                      f"heading `{ident}`")
        heads = {slug(h.text): h.text for h in _walk(
            parse(target.read_text(), str(target))) if h.kind == HEADING}
        if ident not in heads:
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"no heading `{ident}` in `{path}`")
        if text != heads[ident]:
            raise ControlledMarkdownError(node.source, node.line, "link-text",
                                      f"a link to a heading reads as that "
                                      f"heading: `{heads[ident]}`")
