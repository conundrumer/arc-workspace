"""An agent's checklist, `prompts/agents/<agent>/checklist.md`, and the
step command's walk of it. The form of a checklist and what the command
prints for each call are as
[Checklists](prompts/agents/notes/checklists.md#checklists) gives them."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from handbook.agent_documents import agent_dir
from handbook.agents import agent_names
from handbook.context import no_item_named
from handbook.paths import DOCUMENTS_ROOT

CHECKLIST = "checklist.md"


@dataclass(frozen=True)
class Step:
    """An item with no items of its own."""

    heading: nm.Node


@dataclass(frozen=True)
class PartCall:
    """An item that calls a conditional part's file, with the items of that
    part."""

    heading: nm.Node
    file: Path
    items: tuple[Item, ...]


type Item = Step | PartCall


STEP = "uv run python scripts/step.py"


@dataclass(frozen=True)
class Gap:
    """The first item of a walk whose text no step-call result holds, and
    the step call that prints it."""

    item: Item
    call: str


def checklist_file(agent: str, root: Path = DOCUMENTS_ROOT) -> Path:
    return agent_dir(root) / agent / CHECKLIST


def checklist_agents(root: Path = DOCUMENTS_ROOT) -> list[str]:
    """Each agent under `root` that has a checklist, in name order."""
    return [name for name in agent_names(agent_dir(root))
            if checklist_file(name, root).is_file()]


NO_CHECKLIST = mctx("no agent has a checklist")

ENTER = mctx("""
    - Where the condition above holds, run `uv run python scripts/step.py {agent} --enter {item}`.
    - Where it does not hold, run `uv run python scripts/step.py {agent} {item}`.
    """)

NOT_A_CALL = mctx("the item `{item}` calls no conditional part's file")

NO_FILE = mctx("the item `{item}` of {path} has items of its own, and its text does not link exactly one document with no section")

EMPTY = mctx("{path} holds no item")

LAST = mctx("`{item}` is the last item of {path}")


def _own(heading: nm.Node) -> nm.Node:
    """A heading with its text and none of its sections."""
    return replace(heading, children=[c for c in heading.children
                                      if c.kind != nm.HEADING])


def _walk(items: tuple[Item, ...]) -> list[Item]:
    """Every item, each before the items of its part, in order."""
    out: list[Item] = []
    for item in items:
        out.append(item)
        if isinstance(item, PartCall):
            out.extend(_walk(item.items))
    return out


def _find(items: tuple[Item, ...], want: str, after: Item | None
          ) -> tuple[Item, Item | None] | None:
    """The item of `items`, or of their parts, whose id is `want`, with the
    item after it, where `after` is the item after the last of `items`."""
    for n, item in enumerate(items):
        following = items[n + 1] if n + 1 < len(items) else after
        if nm.slug(item.heading.text) == want:
            return item, following
        if isinstance(item, PartCall):
            found = _find(item.items, want, following)
            if found is not None:
                return found
    return None


class Checklist:
    """One agent's checklist, read and parsed."""

    def __init__(self, agent: str, root: Path = DOCUMENTS_ROOT) -> None:
        self.agent = agent
        self.root = root
        self.path = checklist_file(agent, root)
        if not self.path.is_file():
            agents = checklist_agents(root)
            if not agents:
                raise SystemExit(NO_CHECKLIST)
            raise no_item_named("agent with a checklist",
                                "agents with a checklist", agent, agents)
        self.registry = nm.Registry(root)
        self.document = self.registry.load(self.path)
        self.items = self._items(self.document)

    def _label(self) -> str:
        return self.registry.rel(self.document)

    def _items(self, parent: nm.Node) -> tuple[Item, ...]:
        return tuple(self._item(c) for c in parent.children
                     if c.kind == nm.HEADING)

    def _item(self, heading: nm.Node) -> Item:
        items = self._items(heading)
        if not items:
            return Step(heading)
        files = {nm.target_of(path, self.path, self.root)
                   for _node, _text, path, ident in nm.links(_own(heading))
                   if not ident}
        if len(files) != 1:
            raise SystemExit(NO_FILE.format(item=heading.text,
                                              path=self._label()))
        return PartCall(heading, files.pop(), items)

    def named(self, name: str) -> tuple[Item, Item | None]:
        """The item that `name` names, by its heading's text or its id, and
        the item after it, None after the last: its next sibling, or, after
        the last item of a part, the item after that part's call."""
        found = _find(self.items, nm.slug(name), None)
        if found is None:
            raise no_item_named("item", "items", name,
                                [i.heading.text for i in _walk(self.items)])
        return found

    def text(self, item: Item) -> str:
        """An item as the agent receives it: its own text, rendered with its
        links, and, for an item that calls a conditional part's file, the
        calls that enter and skip that part."""
        out = nm.render(nm.section_document(self.document, _own(item.heading)),
                        self.registry)
        if isinstance(item, PartCall):
            out = out.rstrip("\n") + "\n\n" + ENTER.format(
                agent=self.agent, item=nm.slug(item.heading.text))
        return out

    def _walked(self, items: tuple[Item, ...], held: Callable[[str], bool],
                args: tuple[str, ...]) -> Iterator[tuple[Item, tuple[str, ...]]]:
        """Each item of the walk of `items`, with the arguments of the step
        call that prints it, where `args` prints the first of `items`; a
        part's items are in the walk where `held` holds the text of its
        first item. Returns the arguments that print the item after."""
        for item in items:
            yield item, args
            args = (nm.slug(item.heading.text),)
            if isinstance(item, PartCall) and held(self.text(item.items[0])):
                args = yield from self._walked(item.items, held, ("--enter", *args))
        return args

    def gap(self, results: Iterable[str], upto: str | None = None) -> Gap | None:
        """The first item of the walk, up to the item `upto` names or else
        up to the last item, that no result of `results` holds, or None.
        `results` are the results of the agent's step calls, in order. A
        result holds an item where it holds the item's text, both with
        trailing whitespace stripped, and it comes after the last result
        that holds an earlier item of the walk, so a later round that
        prints an item again needs each item after it printed again. A
        part's items are in the walk where a result holds its first item by
        the same rule. Raises `ValueError` where the walk skips the part
        that holds `upto`."""
        texts = [r.rstrip() for r in results]
        # The index of the last result that holds an item of the walk so far.
        last = -1

        def holding(text: str) -> list[int]:
            want = text.rstrip()
            return [n for n, t in enumerate(texts) if n > last and want in t]

        def held(text: str) -> bool:
            return bool(holding(text))

        target = None if upto is None else self.named(upto)[0]
        for item, args in self._walked(self.items, held, ()):
            found = holding(self.text(item))
            if not found:
                return Gap(item, " ".join([STEP, self.agent, *args]))
            last = found[-1]
            if item is target:
                return None
        if target is not None:
            raise ValueError(f"the walk of {self._label()} skips the part that "
                             f"holds `{target.heading.text}`")
        return None

    def first(self) -> str:
        if not self.items:
            raise SystemExit(EMPTY.format(path=self._label()))
        return self.text(self.items[0])

    def after(self, name: str) -> str:
        item, after = self.named(name)
        if after is None:
            return LAST.format(path=self._label(), item=item.heading.text)
        return self.text(after)

    def enter(self, name: str) -> str:
        """The conditional part's file that the item `name` calls, rendered,
        then the first item of that part."""
        item, _ = self.named(name)
        if not isinstance(item, PartCall):
            raise SystemExit(NOT_A_CALL.format(item=item.heading.text))
        part = self.registry.load(item.file)
        return (nm.render(part, self.registry).rstrip("\n") + "\n\n"
                + self.text(item.items[0]))
