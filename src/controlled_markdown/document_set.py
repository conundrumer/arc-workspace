"""The checks of a document set: its closure, its partials, its blocks and
its links, with the links a node's text holds, the file each names, and
the section a slug names, its span and its lines."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from controlled_markdown import (
    ATTRIBUTE,
    CODE,
    COMMENT,
    ControlledMarkdownError,
    HEADING,
    INCLUDE,
    INLINE,
    Node,
    parse,
    QUOTE,
    Registry,
    Rule,
    slug,
    TABLE,
    _walk,
    reference,
    resolve_reference,
)
from controlled_markdown.registry import sections


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
                where = reference(node.attr(name) or "").path
                walk(resolve_reference(where, path))

    walk(entry)
    return out


def carried(node: Node) -> Iterator[Node]:
    """Every node a render shows: the lines under a `comment` are the
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
    the lines a render shows count, so a link under a `comment` is the
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
            for _, _, path, _ in _node_links(node):
                target = target_of(path, file, root)
                if target not in document_set:
                    continue
                if registry.rel(registry.open(target)) not in inside:
                    raise ControlledMarkdownError(
                        source, node.line, Rule.HANDBOOK_LINK,
                        f"`{path}` is a document the handbook does not hold")


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
            ref = reference(value)
            if not ref.ident:
                continue
            target = resolve_reference(ref.path, file)
            out[(target, ref.ident)] = out.get((target, ref.ident), 0) + 1
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
                    heading.source, heading.line, Rule.PARTIAL_SITES,
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
                                          Rule.BLOCK_REPEAT,
                                          "a line holds one code node, "
                                          "quote, or table at most")
            seen = True
        check_blocks(child)


LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
SPAN_RE = re.compile(r"(`[^`]*`)")
# A target outside the repo, and with it a target in the document that
# holds the link, which opens with `#`.
EXTERNAL_RE = re.compile(r"^[a-z][a-z0-9+.-]*:|^//")
SCHEME_RE = re.compile(rf"{EXTERNAL_RE.pattern}|^#")


def _node_links(node: Node, own: bool = False
                ) -> Iterator[tuple[Node, str, str, str]]:
    """Every link in one node's text to a target in the repo that names a
    path, and with `own` every link to a section of the document that holds
    it as well, with an empty path, as (node, text, path, slug). A code
    node holds no link, and a backtick span is literal, so a link written
    inside one is text."""
    if node.kind == CODE:
        return
    for part in SPAN_RE.split(node.text):
        if part.startswith("`"):
            continue
        for m in LINK_RE.finditer(part):
            target = m.group(2)
            if EXTERNAL_RE.match(target):
                continue
            ref = reference(target)
            if ref.path or own:
                yield node, m.group(1), ref.path, ref.ident or ""


def links(node: Node, own: bool = False) -> Iterator[tuple[Node, str, str, str]]:
    """Every link under `node`, as `_node_links` gives the links of each
    node."""
    for child in _walk(node):
        yield from _node_links(child, own)


def relative_link(path: str) -> bool:
    """Whether a link's path is relative to the document that holds it
    (`target_of`)."""
    return path.startswith(("./", "../"))


class RelativeToNoFile(ValueError):
    """A link relative to the file that holds it, in text read from no
    file: a fault in any text (`target_of`)."""


def target_of(path: str, file: Path | None, root: Path | None = None) -> Path:
    """Where a link's target stands. A target that opens with `./` or `../`
    is relative to the document that holds it; every other target is relative
    to the repo root, since that is where a session runs. `file` is None
    where the text was read from no file, and a link with an empty or a
    relative path in such text is a fault."""
    if path and not relative_link(path):
        return ((root or Path.cwd()) / path).resolve()
    if file is None:
        raise RelativeToNoFile(f"`{path}` is relative to text read from no file")
    return resolve_reference(path, file)


def section(document: Node, ident: str) -> Node | None:
    """The heading node of `document` whose id (`registry.sections`) is
    `ident`, with its subtree, or None where no heading has that id."""
    return sections(document, document.source).get(ident)


def section_span(document: Node, heading: Node, length: int) -> tuple[int, int]:
    """The first and last line of the section of `heading`, a heading of
    `document`, whose text has `length` lines: the heading's line to the
    line before the first node that `parse` puts outside the heading's
    subtree after it, or to the last line."""
    inside = {id(n) for n in _walk(heading)}
    end = next((n.line - 1 for n in _walk(document)
                if n.line > heading.line and id(n) not in inside), length)
    return heading.line, max(heading.line, end)


def section_lines(document: Node, heading: Node, lines: list[str]) -> list[str]:
    """The lines of the section of `heading`, a heading of `document`, whose
    text is `lines` (`section_span`), the heading's line first, with each
    line of an attribute (`+ ...`, or the `* ...` of a directive) left
    out."""
    first, last = section_span(document, heading, len(lines))
    attributes = {n.line for n in _walk(heading) if n.kind == ATTRIBUTE}
    return [lines[k - 1] for k in range(first, last + 1) if k not in attributes]


def check_links(document: Node, file: Path, root: Path | None = None) -> None:
    """Every link in the document resolves: the file or directory stands where
    `target_of` puts it, and a slug names a heading of that file whose text the
    link text gives. An external target is skipped."""
    for node, text, path, ident in links(document):
        target = target_of(path, file, root)
        if not target.exists():
            raise ControlledMarkdownError(node.source, node.line, Rule.LINK_MISSING,
                                      f"nothing at `{path}`")
        if not ident:
            continue
        if not target.is_file():
            raise ControlledMarkdownError(node.source, node.line, Rule.LINK_MISSING,
                                      f"`{path}` is a directory and holds no "
                                      f"heading `{ident}`")
        heading = section(parse(target.read_text(), str(target)), ident)
        if heading is None:
            raise ControlledMarkdownError(node.source, node.line, Rule.LINK_MISSING,
                                      f"no heading `{ident}` in `{path}`")
        if text != heading.text:
            raise ControlledMarkdownError(node.source, node.line, Rule.LINK_TEXT,
                                      f"a link to a heading reads as that "
                                      f"heading: `{heading.text}`")
