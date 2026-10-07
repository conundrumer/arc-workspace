"""The registry of Controlled Markdown: the documents a render draws on,
with each document's path and its sections by id."""

from __future__ import annotations

from pathlib import Path

from controlled_markdown.nodes import HEADING, ControlledMarkdownError, Node, Rule, slug
from controlled_markdown.parser import parse


# ---------------------------------------------------------------- registry


class Registry:
    """The documents a render draws on, their paths, and their sections.

    An include or an inline names a file, so the registry reads a document
    the first time one names it, and keys it by its resolved path. `load`
    reads one explicitly, for the document a render starts from.

    An id is scoped to its document: a heading's id is the slug of its text,
    lower case with each run of spaces as one hyphen, and two documents may
    use one name. A collision within a document is settled by renaming a
    heading.

    `root` is the directory the paths a notice names are relative to.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self.documents: dict[str, Node] = {}
        self.ids: dict[str, dict[str, Node]] = {}  # source name -> id -> node
        self.paths: dict[str, str] = {}      # document source name -> path
        self.files: dict[Path, Node] = {}    # resolved path -> document
        self.sources: dict[str, Path] = {}   # source name -> resolved path

    def add(self, name: str, document: Node, path: str = "",
            file: Path | None = None) -> Node:
        """A parsed document under `name`, with `path` as the path a notice
        names and `file` as the path an include resolves against."""
        self.documents[name] = document
        self.paths[name] = path
        self.paths.setdefault(document.source, path)
        rel = path or document.source or name
        self.ids[document.source] = self._index(document, rel)
        if file is not None:
            self.files[file] = document
            self.sources[document.source] = file
        return document

    def load(self, path: Path, name: str | None = None) -> Node:
        """A document read from `path`. The path a notice names is relative to
        the registry's root."""
        path = path.resolve()
        rel = relative(path, self.root)
        return self.add(name or rel, parse(path.read_text(), name or rel),
                        rel, file=path)

    def open(self, path: Path) -> Node:
        """The document at `path`, read the first time an include names it."""
        path = path.resolve()
        document = self.files.get(path)
        return document if document is not None else self.load(path)

    def rel(self, document: Node) -> str:
        """The path a notice names for `document`."""
        return self.paths.get(document.source) or document.source

    def file(self, source: str) -> Path | None:
        """The file a document was read from, which its includes resolve
        against."""
        return self.sources.get(source)

    def _index(self, node: Node, rel: str) -> dict[str, Node]:
        """The sections under `node`, keyed by id: a heading's id is the slug
        of its text."""
        out: dict[str, Node] = {}
        for child in _walk(node):
            if child.kind != HEADING:
                continue
            ident = slug(child.text)
            if not ident:
                continue
            if ident in out:
                raise ControlledMarkdownError(child.source, child.line,
                                          Rule.ID_REPEAT,
                                          f"`{ident}` is already an id in {rel}")
            out[ident] = child
        return out


def _walk(node: Node):
    for child in node.children:
        yield child
        yield from _walk(child)


def relative(path: Path, root: Path | None = None) -> str:
    """A path as `root` sees it, or as given when it lies outside `root` or
    when no root is given."""
    if root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)
