"""The sections a reader's context reaches by chains of links, and the
change to their text between two sides of a change."""

from __future__ import annotations

import difflib
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from controlled_markdown.__main__ import collect, configured, repo_root
from handbook.paths import DOCUMENTS_ROOT


@dataclass(frozen=True, order=True)
class LinkTarget:
    """What a link to a document names: the document, by its path from the
    root of the side it is read on, and the id of one of its sections,
    empty where the link names the whole document."""

    path: Path
    ident: str

    def __str__(self) -> str:
        return f"{self.path}#{self.ident}" if self.ident else str(self.path)


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

    def _render(self, target: LinkTarget) -> tuple[str, list[LinkTarget]] | None:
        file = (self.root / target.path).resolve()
        if file not in self.documents:
            return None
        try:
            document = self.registry.open(file)
        except nm.ControlledMarkdownError as e:
            raise SystemExit(mctx("A document at {where} does not parse: "
                                  "{error}").format(where=self.where, error=e))
        if target.ident:
            node = self.registry.ids[document.source].get(target.ident)
            if node is None:
                return None
            document = nm.section_document(document, node)
        text, found = nm.render_linked(document, self.registry)
        return text, [t for file, ident in found
                      if (t := self._known(file, ident)) is not None]

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

    def chains(self, context: str, goals: set[LinkTarget]
               ) -> dict[LinkTarget, list[tuple[LinkTarget, ...]]]:
        """Each chain of links that leads `context` to a target in `goals`,
        as the targets of its links, the goal last, with no target twice,
        by goal. The chains of a goal come in the order of a depth-first
        walk that takes the links of each text in the order they stand."""
        toward = set(goals)
        sources = self.reached(context)
        while True:
            more = {t for t in sources if t not in toward
                    and any(after in toward for after in self.links(t))}
            if not more:
                break
            toward |= more
        out: dict[LinkTarget, list[tuple[LinkTarget, ...]]] = {g: [] for g in goals}

        def walk(chain: tuple[LinkTarget, ...]) -> None:
            if chain[-1] in goals:
                out[chain[-1]].append(chain)
            for after in self.links(chain[-1]):
                if after in toward and after not in chain:
                    walk((*chain, after))

        for first in self._firsts(context):
            if first in toward:
                walk((first,))
        return out


@dataclass(frozen=True)
class LinkedChange:
    """A link target whose text the change alters, and that a chain of
    links leads a reader's context to: each such chain, as `_Side.chains`
    gives it, those of the checkout first, then those only the commit
    has; and its text on each side, empty where that side has no such
    document or no such section in it."""

    target: LinkTarget
    chains: tuple[tuple[LinkTarget, ...], ...]
    before: str
    after: str

    @property
    def lines(self) -> set[str]:
        return _changed_lines(self.before, self.after)

    def chain_lines(self) -> list[str]:
        """One line for each chain, as `scripts/context.py` `HELP` gives
        it."""
        return [" via ".join(str(t) for t in reversed(chain)) for chain in self.chains]


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
    `scripts/context.py` `HELP` gives as left out."""
    shown = _changed_lines(before, after)
    found: list[LinkedChange] = []
    for target in sorted(set(now.reached(after)) | set(then.reached(before))):
        then_text, now_text = then.text(target) or "", now.text(target) or ""
        change = LinkedChange(target, (), then_text, now_text)
        if then_text != now_text and not change.lines <= shown:
            found.append(change)
    goals = {c.target for c in found}
    now_chains, then_chains = now.chains(after, goals), then.chains(before, goals)
    found = [LinkedChange(c.target, tuple(dict.fromkeys(
                 now_chains[c.target] + then_chains[c.target])), c.before, c.after)
             for c in found]
    whole = {c.target.path: c.lines for c in found if not c.target.ident}
    return [c for c in found if not c.target.ident
            or not c.lines <= whole.get(c.target.path, set())]


def sides(tree: Path, commit: str) -> tuple[_Side, _Side]:
    return _Side(tree, commit), _Side(DOCUMENTS_ROOT, "the checkout")
