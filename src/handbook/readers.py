"""The readers the `context` command knows, and their contexts at a commit
and the diff of each since one, with the diff of each section a reader
reaches by links."""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
import tempfile
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from controlled_markdown.__main__ import collect, configured, repo_root
from engine import checkout
from handbook.agents import agent_dir, agent_names
from handbook.context import role_dir, role_stems, workflow_dir, workflow_names
from handbook.contexts import (agent_context, codex_context, console_context,
                               console_stages, role_context, session_context,
                               survey_context, workflow_context)
from handbook.coordinator_document import coordinator_context
from handbook.paths import DOCUMENTS_ROOT, REPO_ROOT


class ArgumentForm(StrEnum):
    """The argument a reader of the `context` command takes, as its usage
    line writes it."""

    NAME = "<name>"
    STAGE = "<stage>"


@dataclass(frozen=True)
class Reader:
    """A reader the `context` command knows: the form of the argument it
    takes, None where it takes none; the values that argument takes, from
    the documents root they are listed under; and its context, from the
    arguments."""

    form: ArgumentForm | None
    values: Callable[[Path], list[str]]
    context: Callable[[list[str]], str]


def _no_values(_root: Path) -> list[str]:
    return []


def _console_stages(root: Path) -> list[str]:
    """The console's stages, which `console_stages` lists only under
    `DOCUMENTS_ROOT`: another root is a fault."""
    if root != DOCUMENTS_ROOT:
        raise ValueError(f"the console's stages are listed under {DOCUMENTS_ROOT} alone, "
                         f"not under {root}")
    return console_stages()


CONTEXT_READERS = {
    "coordinator": Reader(None, _no_values, lambda _a: coordinator_context()),
    "session": Reader(None, _no_values, lambda _a: session_context()),
    "codex": Reader(None, _no_values, lambda _a: codex_context()),
    "agent": Reader(ArgumentForm.NAME, lambda r: agent_names(agent_dir(r)),
                    lambda a: agent_context(a[0])),
    "role": Reader(ArgumentForm.NAME, lambda r: role_stems(role_dir(r)),
                   lambda a: role_context(a[0])),
    "console": Reader(ArgumentForm.STAGE, _console_stages,
                      lambda a: console_context(a[0])),
    "survey": Reader(None, _no_values, lambda _a: survey_context()),
    "workflow": Reader(ArgumentForm.NAME, lambda r: workflow_names(workflow_dir(r)),
                       lambda a: workflow_context(a[0])),
}
"""Each reader the `context` command knows, by name."""


def _calls(name: str, form: str | None,
           values: list[str]) -> list[tuple[str, list[str]]]:
    return [(name, [v]) for v in values] if form else [(name, [])]


def reader_calls() -> list[tuple[str, list[str]]]:
    """Each reader the `context` command knows, with each argument list it
    takes."""
    return [call for name, reader in CONTEXT_READERS.items()
            for call in _calls(name, reader.form, reader.values(DOCUMENTS_ROOT))]


def _command(reader: str, args: list[str]) -> str:
    """The `context` command line that prints one reader's context."""
    return " ".join(["context", reader, *args])


def _usage(reader: str, form: ArgumentForm | None) -> str:
    return _command(reader, [form] if form else [])


def contexts_text() -> str:
    """Every reader the `context` command knows, one per line: its name, its
    argument form, and the values that argument takes."""
    out = []
    for name, reader in CONTEXT_READERS.items():
        head = _usage(name, reader.form)
        names = reader.values(DOCUMENTS_ROOT)
        out.append(f"{head:<24}{', '.join(names)}".rstrip())
    return "\n".join(out) + "\n"


def context_text(reader: str, args: list[str]) -> str:
    """One reader's whole context, in the order it arrives."""
    if reader not in CONTEXT_READERS:
        raise SystemExit("no reader named "
                         f"`{reader}`\n{contexts_text()}".rstrip())
    known = CONTEXT_READERS[reader]
    form = known.form
    if len(args) != (1 if form else 0):
        raise SystemExit(f"usage: {_usage(reader, form)}")
    return known.context(args)


CONTEXT_SCRIPT = (checkout.scripts() / "context.py").relative_to(checkout.ROOT)
"""The command that prints a reader's context, from a checkout's root."""


@contextmanager
def _tree_at(commit: str) -> Iterator[Path]:
    """The tree of `commit`, checked out as a detached git worktree of the
    repository in a temporary directory, so that the checkout stays as it
    is and the commit's own code finds the main worktree as in any other
    checkout. The worktree is removed on every exit of the block and leaves
    no entry in `git worktree list`."""
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        try:
            checkout.git_out(REPO_ROOT, "worktree", "add", "--detach",
                             str(tree), commit)
        except checkout.GitFailed as e:
            raise SystemExit(e.stderr.strip())
        try:
            yield tree
        finally:
            checkout.git_out(REPO_ROOT, "worktree", "remove", "--force", str(tree))


def _run_in(tree: Path, commit: str, argv: list[str]) -> str:
    """The output of `scripts/context.py` with `argv`, run in `tree`, the
    tree of `commit`, with that tree's own code."""
    paths = [str(tree / "src"), os.environ.get("PYTHONPATH", "")]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in paths if p)}
    done = subprocess.run([sys.executable, str(tree / CONTEXT_SCRIPT), *argv],
                          cwd=tree, env=env, capture_output=True, text=True)
    if done.returncode != 0:
        failed = mctx("The run of `{command}` at {commit} failed.").format(
            command=" ".join(argv), commit=commit)
        raise SystemExit(f"{failed}\n{done.stderr.strip()}")
    return done.stdout


def _render_in(tree: Path, commit: str, reader: str, args: list[str]) -> str:
    """One reader's whole context as `tree`, the tree of `commit`, renders
    it."""
    return _run_in(tree, commit, ["context", reader, *args])


def context_at(commit: str, reader: str, args: list[str]) -> str:
    """One reader's whole context as the tree of `commit` renders it, with
    that tree's own code, run in a detached worktree of `commit`
    (`_tree_at`)."""
    with _tree_at(commit) as tree:
        return _render_in(tree, commit, reader, args)


def _unified(before: str, after: str, head: str, commit: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"{head} at {commit}", tofile=head))


def context_diff(commit: str, reader: str, args: list[str]) -> str:
    """The unified diff from one reader's context at `commit`, as
    `context_at` renders it in a detached worktree of `commit`, to its
    context in the checkout, then the unified diff of the text of each
    target it reaches by links that the change alters, as
    `_linked_changes` finds them, under one line for each chain that
    leads to it (`LinkedChange.chain_lines`). Empty where none of these differ. A side that does not
    define the reader, as `contexts_diff` finds it, gives an empty
    context, so the diff of an added reader gains every line and that of a
    removed one loses every line (`_side_contexts`). A render that fails is
    a fault."""
    call = (reader, args)
    with _tree_at(commit) as tree:
        then = _renders_in(tree, commit, [c for c in _calls_in(tree, commit) if c == call])
        before, after = _side_contexts(call, then, call in reader_calls())
        linked = _linked_changes(before, after, *_sides(tree, commit))
    return (_unified(before, after, _command(reader, args), commit)
            + "".join("".join(f"{line}\n" for line in c.chain_lines())
                      + _unified(c.before, c.after, str(c.target), commit)
                      for c in linked))


def _renders_in(tree: Path, commit: str,
                calls: list[tuple[str, list[str]]]) -> dict[str, str]:
    """The context of each of `calls` as `tree`, the tree of `commit`,
    renders it, by its `context` command line, the renders run in
    parallel."""
    with ThreadPoolExecutor() as pool:
        befores = list(pool.map(lambda c: _render_in(tree, commit, *c), calls))
    return {_command(*c): before for c, before in zip(calls, befores, strict=True)}


def _side_contexts(call: tuple[str, list[str]], then: dict[str, str],
                   now: bool) -> tuple[str, str]:
    """A reader's context at the commit and in the checkout, from `then`,
    the contexts of the readers the commit defines as `_renders_in` gives
    them, and `now`, whether the checkout defines the reader. A side that
    does not define the reader gives an empty context, and a reader neither
    side defines is a fault (`context_text`)."""
    before = then.get(_command(*call))
    after = context_text(*call) if now or before is None else ""
    return "" if before is None else before, after


CONTEXTS_LINE_RE = re.compile(r"context (\S+)(?: (<[^>]*>))? *(.*)")
"""A line of `contexts_text`: the reader, its argument form, and the values
that argument takes."""


def _calls_in(tree: Path, commit: str) -> list[tuple[str, list[str]]]:
    """Each reader the `context` command of `tree`, the tree of `commit`,
    knows, with each argument list it takes, read from that tree's
    `contexts` output, the one form a commit's own code is known to
    give them in."""
    calls: list[tuple[str, list[str]]] = []
    for line in _run_in(tree, commit, ["contexts"]).splitlines():
        match = CONTEXTS_LINE_RE.fullmatch(line)
        if not match:
            raise SystemExit(mctx("A line of `contexts` at {commit} is not a "
                                  "reader: {line}").format(commit=commit, line=line))
        name, form, values = match.groups()
        calls += _calls(name, form, [v for v in values.split(", ") if v])
    return calls


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
    holder = nm.Node(nm.DOCUMENT)
    holder.children = [nm.Node(nm.CONTENT, text=line)
                       for line in nm.outside_fences(text)]
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
        """The target `ident` of `file`; None where `file` is no document of
        the set."""
        if file not in self.documents:
            return None
        return LinkTarget(file.relative_to(self.root.resolve()), ident)

    def target(self, path: str, ident: str) -> LinkTarget | None:
        """The target of a link with `path` and `ident` in a reader's
        context; None where the link names no document of the set. A
        context is read from no file, so a link relative to the file that
        holds it is a fault."""
        if nm.relative_to_no_file(path, None):
            raise SystemExit(mctx("A context at {where} links `{path}`, relative "
                                  "to no file.").format(where=self.where, path=path))
        return self._known(nm.target_of(path, None, self.root), ident)

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
            document = nm.Node(nm.DOCUMENT, source=document.source)
            document.children = [node]
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


def _linked_changes(before: str, after: str, then: _Side,
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


class ReaderChange(StrEnum):
    """How a change alters a reader's context: only the checkout defines
    the reader, only the commit does, both do and its contexts differ, or
    both do and only the text of a target it reaches by links differs
    (`_linked_changes`)."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    LINKED = "linked"


def _sides(tree: Path, commit: str) -> tuple[_Side, _Side]:
    return _Side(tree, commit), _Side(DOCUMENTS_ROOT, "the checkout")


def contexts_diff(commit: str) -> str:
    """Each reader, with its arguments, whose context the change since
    `commit` alters, or the text of a target it reaches by links, one per
    line, marked with its `ReaderChange` other than `CHANGED`, and after
    it, one indented line for each chain that leads to each target whose
    text the change alters, as `_linked_changes` finds them
    (`LinkedChange.chain_lines`). A reader both sides define is altered
    where its context at `commit`, as `context_at` renders it in a detached
    worktree of `commit`, differs from its context in the checkout; a
    render at `commit` that fails is a fault. A side that does not define
    a reader gives it an empty context (`_side_contexts`).
    The checkout's readers come first, in `reader_calls` order, then the
    ones only the commit defines."""
    now = reader_calls()
    with _tree_at(commit) as tree:
        then = _calls_in(tree, commit)
        rendered = _renders_in(tree, commit, then)
        changes = [(c, ReaderChange.ADDED if c not in then else ReaderChange.CHANGED)
                   for c in now]
        changes += [(c, ReaderChange.REMOVED) for c in then if c not in now]
        then_side, now_side = _sides(tree, commit)
        out = []
        for (reader, args), change in changes:
            command = _command(reader, args)
            before, after = _side_contexts((reader, args), rendered,
                                           change is not ReaderChange.REMOVED)
            linked = _linked_changes(before, after, then_side, now_side)
            if change is ReaderChange.CHANGED and before == after:
                if not linked:
                    continue
                change = ReaderChange.LINKED
            mark = "" if change is ReaderChange.CHANGED else f" ({change})"
            out.append(f"{command}{mark}\n")
            out += [f"    {line}\n" for c in linked for line in c.chain_lines()]
    return "".join(out)
