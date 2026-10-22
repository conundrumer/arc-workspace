"""An agent's checklist, `prompts/agents/<agent>/checklist.md`, and the
step command's walk of it. The form of a checklist and what the command
prints for each call, including the next isolated step call or the last-item
line, are as
[Checklists](prompts/agents/notes/checklists.md#checklists) gives them."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from enum import StrEnum
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


STEP_SCRIPT = "scripts/step.py"
"""The script of the step calls, from the root of the tree."""


class Entry(StrEnum):
    """How a step call enters the part its item calls: with the part's
    file, or, for a reader whose context still holds that file, without
    it."""
    ENTER = "--enter"
    REENTER = "--reenter"


def step_call(agent: str, item: str | None = None, entry: Entry | None = None) -> str:
    """The step call of `agent`, `uv run python scripts/step.py <agent>
    [--enter|--reenter] <item>`, on the item `item` with `entry`, or, where
    `item` is None, the call that prints the first item."""
    return " ".join(["uv", "run", "python", STEP_SCRIPT, agent,
                     *([] if entry is None else [entry.value]),
                     *([] if item is None else [item])])


@dataclass(frozen=True)
class Gap:
    """The first item no step-call result holds, and the call that prints it."""

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
    - Where the condition above holds, once this item is done, as a Bash call by itself, run `{enter}`, or, where your context still holds this part's file from an earlier entry, `{reenter}`.
    - Where it does not hold, once this item is done, as a Bash call by itself, run `{skip}`.
    """)

NEXT = mctx("Once this item is done, run `{call}` as a Bash call by itself.")

NOT_A_CALL = mctx("the item `{item}` calls no conditional part's file")

NO_FILE = mctx("the item `{item}` of {path} has items of its own, and its text does not link exactly one document with no section")

EMPTY = mctx("{path} holds no item")

STOP = mctx("""
    - Your walk stops at the item `{item}`.
    - Your report gives that item and each item after it as unfinished, with what keeps you from doing that item as the reason.
    - Once a later message lets you do that item, run `{call}`, then take the steps from the item it prints.
    - Your checklist's last item follows.
    """)

LAST = mctx("`{item}` is the last item of {path}")


def _own(heading: nm.Node) -> nm.Node:
    """A heading with its text and none of its sections."""
    return replace(heading, children=[c for c in heading.children
                                      if c.kind != nm.HEADING])


def walk(items: tuple[Item, ...]) -> list[Item]:
    """Every item, each before the items of its part, in order."""
    out: list[Item] = []
    for item in items:
        out.append(item)
        if isinstance(item, PartCall):
            out.extend(walk(item.items))
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
                                [i.heading.text for i in walk(self.items)])
        return found

    def text(self, item: Item) -> str:
        """An item as the agent receives it: its own text, rendered with its
        links, and, for an item that calls a conditional part's file, the
        calls that enter and skip that part; each other item ends with its
        next call or the line that it is the last item."""
        out = nm.render(nm.section_document(self.document, _own(item.heading)),
                        self.registry)
        if isinstance(item, PartCall):
            slug = nm.slug(item.heading.text)
            out = out.rstrip("\n") + "\n\n" + ENTER.format(
                enter=step_call(self.agent, slug, Entry.ENTER),
                reenter=step_call(self.agent, slug, Entry.REENTER),
                skip=step_call(self.agent, slug))
        else:
            _, following = self.named(item.heading.text)
            footer = (LAST.format(item=item.heading.text, path=self._label())
                      if following is None else NEXT.format(
                          call=step_call(self.agent, nm.slug(item.heading.text))))
            out = out.rstrip("\n") + "\n\n" + footer
        return out

    def _walked(self, items: tuple[Item, ...], held: Callable[[str], bool],
                call: str, opens: PartCall | None = None
                ) -> Iterator[tuple[Item, str, PartCall | None]]:
        """Each item of the walk of `items`, with the step call that prints
        it, where `call` prints the first of `items`, and the part call
        `opens` for the first of `items`, None for the rest; a part's items
        are in the walk where `held` holds the text of its first item.
        Returns the step call that prints the item after."""
        for item in items:
            yield item, call, opens
            opens = None
            slug = nm.slug(item.heading.text)
            call = step_call(self.agent, slug)
            if isinstance(item, PartCall) and held(self.text(item.items[0])):
                call = yield from self._walked(item.items, held,
                                               step_call(self.agent, slug, Entry.ENTER), item)
        return call

    def gap(self, results: Iterable[str], upto: str | None = None) -> Gap | None:
        """The first item of the walk, up to the item `upto` names or else
        up to the last item, that no result of `results` holds, or None.
        `results` are the results of the agent's step calls, in order. The
        place of an item is a result and the end of the item's text in it.
        An item is held by its text, both with trailing whitespace stripped,
        where it stands after the place of the item before it: in a later
        result, or later in the same result. Its place is then in the last
        result where its text so stands, at the first such stand there, so a
        later round that prints an item again needs each item after it
        printed again. A part's items are in the walk where a result holds
        its first item by the same rule, and a result at or before the one
        that holds that item holds the part's file as `enter` renders it;
        where none does, the gap is that first item. Raises `ValueError`
        where the walk skips the part that holds `upto`."""
        texts = [r.rstrip() for r in results]
        # The place of the last item of the walk so far: the index of its
        # result, and the end of its text there.
        at, end = -1, 0

        def holding(text: str) -> tuple[int, int] | None:
            want = text.rstrip()
            for n in range(len(texts) - 1, max(at, 0) - 1, -1):
                found = texts[n].find(want, end if n == at else 0)
                if found >= 0:
                    return n, found + len(want)
            return None

        def held(text: str) -> bool:
            return holding(text) is not None

        target = None if upto is None else self.named(upto)[0]
        walk = self._walked(self.items, held, step_call(self.agent))
        for item, call, opens in walk:
            place = holding(self.text(item))
            if place is None or (opens is not None and not any(
                    self._file(opens) in t for t in texts[:place[0] + 1])):
                return Gap(item, call)
            at, end = place
            if item is target:
                return None
        if target is not None:
            raise ValueError(f"the walk of {self._label()} skips the part that "
                             f"holds `{target.heading.text}`")
        return None

    def call(self, name: str) -> str:
        """The step call that prints the item `name` names, in the walk that
        enters every part."""
        target = self.named(name)[0]
        for item, call, _ in self._walked(self.items, lambda _: True, step_call(self.agent)):
            if item is target:
                return call
        raise AssertionError(f"the walk that enters every part skips `{name}`")

    def stop(self, name: str) -> str:
        """What the step command prints for a stop at the item `name`: the
        stop, the call that takes the walk on from that item, and the text
        of the checklist's last item."""
        item = self.named(name)[0]
        return STOP.format(item=item.heading.text, call=self.call(name)) \
            + "\n\n" + self.text(self.items[-1])

    def first(self) -> str:
        if not self.items:
            raise SystemExit(EMPTY.format(path=self._label()))
        return self.text(self.items[0])

    def after(self, name: str) -> str:
        item, after = self.named(name)
        if after is None:
            return LAST.format(path=self._label(), item=item.heading.text)
        return self.text(after)

    def _part(self, name: str) -> PartCall:
        item, _ = self.named(name)
        if not isinstance(item, PartCall):
            raise SystemExit(NOT_A_CALL.format(item=item.heading.text))
        return item

    def _file(self, item: PartCall) -> str:
        return nm.render(self.registry.load(item.file), self.registry).rstrip()

    def enter(self, name: str) -> str:
        """The conditional part's file that the item `name` calls, rendered,
        then the first item of that part."""
        item = self._part(name)
        return self._file(item) + "\n\n" + self.text(item.items[0])

    def reenter(self, name: str) -> str:
        """The first item of the conditional part that the item `name`
        calls, without that part's file."""
        return self.text(self._part(name).items[0])
