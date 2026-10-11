"""The sections a reader's context reaches by chains of links, and the
change to their text between two sides of a change."""

from __future__ import annotations

import difflib
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from controlled_markdown.__main__ import collect, configured, repo_root
from handbook.paths import DOCUMENTS_ROOT


class WalkStart(StrEnum):
    """The text a walk of links starts from, as the source a link line gives
    for a link that stands in it."""

    CONTEXT = "context"
    """A reader's context."""
    INSTRUCTIONS = "CLAUDE.md"
    """The project instructions."""


@dataclass(frozen=True, order=True)
class LinkTarget:
    """What a link to a document names: the document, by its path from the
    root of the side it is read on, and the id of one of its sections,
    empty where the link names the whole document."""

    path: Path
    ident: str

    def __str__(self) -> str:
        return f"{self.path}#{self.ident}" if self.ident else str(self.path)


@dataclass(frozen=True)
class Link:
    """A link from the text of `source`, None where the link stands in the
    text a walk of links starts from, to `target`."""

    source: LinkTarget | None
    target: LinkTarget

    def line(self, start: WalkStart) -> str:
        """The link's line, as `scripts/context.py` `HELP` gives it, with
        `start` as the source of a link in the text the walk starts
        from."""
        return f"{self.target} via {start if self.source is None else self.source}"


def link_lines(links: Iterable[tuple[Link, WalkStart]]) -> list[str]:
    """The line of each link, with the start it is given, each once,
    sorted."""
    return sorted({link.line(start) for link, start in links})


def _text_links(text: str) -> Iterator[tuple[str, str]]:
    """Every link in a rendered text, as its path and its id, as
    `controlled_markdown`'s `links` finds them in each line outside a
    fenced code block."""
    holder = nm.Node(nm.DOCUMENT, children=[nm.Node(nm.CONTENT, text=line)
                                            for line in nm.outside_fences(text)])
    for _node, _label, path, ident in nm.links(holder):
        yield path, ident


class _Side:
    """The documents of one side of a change, read under `root`, the tree
    `where` names: the document set its `[tool.controlled_markdown]` table
    names, and the text of each link target as the checkout's
    `controlled_markdown` renders it with the targets of its links, None
    where the side has no such document or no such section in it."""

    def __init__(self, root: Path, where: str) -> None:
        self.root = root
        self.where = where
        if repo_root(root).resolve() != root.resolve():
            raise SystemExit(mctx("No document set is configured at {root}, "
                                  "{where}.").format(root=root, where=where))
        self.documents = {p.resolve() for p in collect(configured(root))}
        self.registry = nm.Registry(root)
        self.rendered: dict[LinkTarget, tuple[str, list[LinkTarget]] | None] = {}

    def _known(self, file: Path, ident: str) -> LinkTarget | None:
        if file not in self.documents:
            return None
        return LinkTarget(file.relative_to(self.root.resolve()), ident)

    def target(self, path: str, ident: str) -> LinkTarget | None:
        """The target of a link with `path` and `ident` in a reader's
        context; None where the link names no document of the set. A
        context is read from no file, so a link relative to the file that
        holds it is a fault."""
        try:
            file = nm.target_of(path, None, self.root)
        except nm.RelativeToNoFile:
            raise SystemExit(mctx("A context at {where} links `{path}`, relative "
                                  "to no file.").format(where=self.where, path=path))
        return self._known(file, ident)

    def _rendering(self, target: LinkTarget) -> tuple[str, list[LinkTarget]] | None:
        if target not in self.rendered:
            self.rendered[target] = self._render(target)
        return self.rendered[target]

    def text(self, target: LinkTarget) -> str | None:
        """The text of `target` on this side; None where the side has no
        such document or no such section in it."""
        rendering = self._rendering(target)
        return None if rendering is None else rendering[0]

    def _opened(self, target: LinkTarget) -> tuple[nm.Node, nm.Node | None] | None:
        """The document of `target` on this side, and the heading node of
        its section, None where it names the whole document; None where the
        side has no such document or no such section in it."""
        file = (self.root / target.path).resolve()
        if file not in self.documents:
            return None
        try:
            document = self.registry.open(file)
        except nm.ControlledMarkdownError as e:
            raise SystemExit(mctx("A document at {where} does not parse: "
                                  "{error}").format(where=self.where, error=e))
        if not target.ident:
            return document, None
        node = self.registry.ids[document.source].get(target.ident)
        return None if node is None else (document, node)

    def _render(self, target: LinkTarget) -> tuple[str, list[LinkTarget]] | None:
        opened = self._opened(target)
        if opened is None:
            return None
        document, node = opened
        if node is not None:
            document = nm.section_document(document, node)
        text, found = nm.render_linked(document, self.registry)
        return text, [t for file, ident in found
                      if (t := self._known(file, ident)) is not None]

    def holders(self, target: LinkTarget) -> frozenset[LinkTarget] | None:
        """The targets whose text holds the text of `target` on this side,
        by heading depth in its document: the whole document and each
        section above it; None where the side has no such document or no
        such section in it."""
        opened = self._opened(target)
        if opened is None:
            return None
        document, node = opened
        if node is None:
            return frozenset()
        idents = {id(n): ident for ident, n in
                  self.registry.ids[document.source].items()}

        def above(parent: nm.Node) -> list[nm.Node] | None:
            for child in parent.children:
                if child is node:
                    return []
                if (path := above(child)) is not None:
                    return [child, *path]
            return None

        path = above(document)
        if path is None:
            raise SystemExit(mctx("The section {target} at {where} stands in no "
                                  "heading of its document.").format(
                                      target=target, where=self.where))
        headings = [n for n in path if n.kind == nm.HEADING]
        if any(id(n) not in idents for n in headings):
            raise SystemExit(mctx("A heading above the section {target} at "
                                  "{where} has no id.").format(
                                      target=target, where=self.where))
        return frozenset({LinkTarget(target.path, ""),
                          *(LinkTarget(target.path, idents[id(n)]) for n in headings)})

    def links(self, target: LinkTarget) -> list[LinkTarget]:
        """The targets the links in the text of `target` name, a link to
        a section of its own document included."""
        rendering = self._rendering(target)
        return [] if rendering is None else rendering[1]

    def _firsts(self, context: str) -> list[LinkTarget]:
        """The targets the links in `context` name, each once, in the order
        the context first links them."""
        found = (self.target(path, ident) for path, ident in _text_links(context))
        return list(dict.fromkeys(t for t in found if t is not None))

    def reached(self, context: str) -> list[LinkTarget]:
        """Each target a chain of links leads `context` to: a chain's first
        link stands in the context, and each later one in the text of the
        target of the one before."""
        seen = dict.fromkeys(self._firsts(context))
        queue: deque[LinkTarget] = deque(seen)
        while queue:
            for after in self.links(queue.popleft()):
                if after not in seen:
                    seen[after] = None
                    queue.append(after)
        return list(seen)

    def leading(self, context: str, goals: set[LinkTarget]) -> set[Link]:
        """Each link that stands on a walk of links from `context` to a
        target in `goals`, a walk that may pass a target twice: a link in
        the context or in the text of a target `reached` gives, whose
        target is a goal or leads by links to one."""
        reached = self.reached(context)
        into: dict[LinkTarget, list[LinkTarget]] = {}
        for source in reached:
            for after in self.links(source):
                into.setdefault(after, []).append(source)
        toward = goals & set(reached)
        queue: deque[LinkTarget] = deque(toward)
        while queue:
            for source in into.get(queue.popleft(), []):
                if source not in toward:
                    toward.add(source)
                    queue.append(source)
        return ({Link(None, t) for t in self._firsts(context) if t in toward}
                | {Link(source, after) for source in reached
                   for after in self.links(source) if after in toward})


@dataclass(frozen=True)
class LinkedChange:
    """A link target whose text the change alters, and that links lead a
    reader's context to: its text on each side, empty where that side has
    no such document or no such section in it; and the targets that hold
    its text on each side that has it (`_Side.holders`)."""

    target: LinkTarget
    before: str
    after: str
    within: frozenset[LinkTarget]

    @property
    def lines(self) -> set[str]:
        return _changed_lines(self.before, self.after)


def _changed_lines(before: str, after: str) -> set[str]:
    """The lines a unified diff from `before` to `after` removes and adds,
    each with its `-` or `+`, the blank ones left out."""
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(),
                                lineterm="", n=0)
    return {line for line in diff
            if line[:1] in "+-" and line[1:].strip()
            and not line.startswith(("+++", "---"))}


def linked_changes(before: str, after: str, then: _Side,
                    now: _Side) -> list[LinkedChange]:
    """Each link target a reader with the context `before` at the commit
    and `after` in the checkout reaches on either side, whose text differs
    between the sides, in target order, other than the ones
    `scripts/context.py` `HELP` gives as left out, before `folded`."""
    shown = _changed_lines(before, after)
    found: list[LinkedChange] = []
    for target in sorted(set(now.reached(after)) | set(then.reached(before))):
        then_text, now_text = then.text(target) or "", now.text(target) or ""
        if then_text == now_text or _changed_lines(then_text, now_text) <= shown:
            continue
        holders = [h for h in (then.holders(target), now.holders(target))
                   if h is not None]
        found.append(LinkedChange(target, then_text, now_text,
                                  frozenset.intersection(*holders)))
    return found


def folded(changes: list[LinkedChange]) -> list[LinkedChange]:
    """`changes`, whose diffs run between the same two commits, with each
    one whose text another of them holds (`LinkedChange.within`) left out,
    in target order."""
    present = {c.target: c for c in changes}
    return [c for c in changes
            if not any(t in present and not present[t].within & present.keys()
                       for t in c.within)]


def sides(tree: Path, commit: str) -> tuple[_Side, _Side]:
    return _Side(tree, commit), _Side(DOCUMENTS_ROOT, "the checkout")
