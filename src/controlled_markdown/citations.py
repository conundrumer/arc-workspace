"""The checks of the documents a code file cites: each path that a string
stands for stands in the tree, each citation of a docstring or a comment
cites its document by its path from the root of the tree, each citation in
the engine cites a file a commit of the tree takes, and each anchor of a
citation refers to a heading of the cited file."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

from controlled_markdown import (
    ControlledMarkdownError,
    code_prose_lines,
    Rule,
    slug,
)
from controlled_markdown.renderers import markdown_heading_lines


# A path a document takes in the repo: the shapes the document set uses, so a
# literal that names one is checked against the tree.
DOC_PATH_RE = re.compile(
    r"^(?:docs/[\w./-]+\.md|prompts/[\w./-]+\.md|CLAUDE\.md"
    r"|\.claude/[\w./-]+\.md)$")


def _named_paths(path: Path, text: str):
    """Every string a file holds that stands for a document, with its line.
    A string holding a hole or a wildcard stands for a shape and is passed
    over."""
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
    """Every document a string of a file stands for by its path stands in
    the tree. A path that goes stale is a reference no reader can
    follow."""
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
    """The fault of an anchor that refers to no heading of the cited file. The
    headings are read from the file's text, since a cited spec file stands
    outside the document set."""
    if anchor in {slug(heading) for _, _, heading in
                  markdown_heading_lines((root / name).read_text())}:
        return None
    return ControlledMarkdownError(source, at, Rule.CITATION_ANCHOR,
                                   f"`{citation}` names no heading of `{name}`")


def check_citations(path: Path, source: str, root: Path,
                    present: frozenset[str]) -> Iterator[ControlledMarkdownError]:
    """Every citation a file of the engine holds cites a file of `present`,
    the files a commit of the tree takes, and its anchor, where it has one,
    refers to a heading of that file. A citation of a file a clone does not hold is
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
    """Every anchor of a citation the file holds refers to a heading of the
    cited file, where the tree holds that file. Code outside the engine
    cites untracked files by path on purpose, so a cited file that is
    absent is passed over."""
    for at, citation, name, anchor in _citations(path):
        if anchor and (root / name).is_file() and (
                err := _anchor_fault(source, at, citation, name, anchor, root)):
            yield err


# A word that cites a document by its file name alone: a name that ends in
# `.md` and that no `/`, `.`, `-` or word character precedes.
BARE_CITATION_RE = re.compile(r"(?<![/.\w-])\w[\w-]*\.md(?![\w-])")


def check_citation_paths(path: Path, source: str,
                         present: frozenset[str]) -> Iterator[ControlledMarkdownError]:
    """A finding at each line of a docstring or a comment of `path`, as
    `code_prose_lines` reads them, that cites a document by its file name
    alone, where a file of `present`, the files a commit of the tree takes,
    has that name and no file at the root of the tree does. The message
    gives the path of each such file."""
    for line, text in code_prose_lines(path):
        for m in BARE_CITATION_RE.finditer(text):
            name = m.group(0)
            if name in present:
                continue
            paths = sorted(p for p in present if p.endswith(f"/{name}"))
            if paths:
                yield ControlledMarkdownError(
                    source, line, Rule.CITATION_PATH,
                    f"`{name}` cites a document by its file name alone; a "
                    f"citation gives its path from the root of the tree: "
                    f"{', '.join(f'`{p}`' for p in paths)}")
