"""A reader's context rendered in a tree of a commit, and its diff since
that commit, with the diff of each section it reaches by links; and the
diff of what a running reader holds, its context and the project
instructions Claude Code gives it beside its context."""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.linked import LinkedChange, LinkTarget, linked_changes, sides
from handbook.paths import DOCUMENTS_ROOT, REPO_ROOT
from handbook.readers import (calls_of, context_command, context_text, reader_calls,
                              reader_named)


CONTEXT_SCRIPT = (checkout.scripts() / "context.py").relative_to(checkout.ROOT)
"""The command that prints a reader's context, from a checkout's root."""

PROJECT_INSTRUCTIONS = Path("CLAUDE.md")
"""The project instructions, from a checkout's root: the file Claude Code
puts in the context of each session and subagent in the checkout, beside
the session's or the agent's own context."""


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


@dataclass(frozen=True)
class _TextDiff:
    """A text a reader holds whole, at `commit` and in the checkout, under
    `head`, with each change to a target it reaches by links, as
    `linked_changes` finds them."""

    head: str
    commit: str
    before: str
    after: str
    linked: list[LinkedChange]


def _text_diff(head: str, before: str, after: str, tree: Path,
               commit: str) -> _TextDiff:
    """The diff of a text from `before`, at `commit`, whose tree is `tree`,
    to `after`, in the checkout."""
    return _TextDiff(head, commit, before, after,
                     linked_changes(before, after, *sides(tree, commit)))


def _diff_text(diffs: list[_TextDiff]) -> str:
    """The unified diff of each text of `diffs`, then the unified diff of
    each target they reach by links, in target order, under one line for
    each chain that leads to it (`LinkedChange.chain_lines`). A target
    whose change two of them give with the same text on each side stands
    once, under the chains of both, and a target that is one of the texts
    stands only as that text, which the reader holds whole. Empty where none
    of these differ."""
    held = {d.head for d in diffs}
    linked: dict[tuple[LinkTarget, str, str], tuple[str, list[str]]] = {}
    for d in diffs:
        for c in d.linked:
            if str(c.target) in held:
                continue
            commit, lines = linked.setdefault((c.target, c.before, c.after),
                                              (d.commit, []))
            lines += [line for line in c.chain_lines() if line not in lines]
    return ("".join(_unified(d.before, d.after, d.head, d.commit) for d in diffs)
            + "".join("".join(f"{line}\n" for line in lines)
                      + _unified(before, after, str(target), commit)
                      for (target, before, after), (commit, lines)
                      in sorted(linked.items(), key=lambda item: item[0][0])))


def _context_sides(tree: Path, commit: str, reader: str,
                   args: list[str]) -> tuple[str, str]:
    """One reader's context at `commit`, as `context_at` renders it in
    `tree`, the tree of `commit`, and in the checkout. The contexts of a
    reader one side does not define, as `contexts_diff` finds it, are those
    `_side_contexts` gives, so the diff of an added reader gains every line
    and that of a removed one loses every line. A render that fails is a
    fault."""
    call = (reader, args)
    then = _renders_in(tree, commit, [c for c in _calls_in(tree, commit) if c == call])
    return _side_contexts(call, then, call in reader_calls())


def context_diff(commit: str, reader: str, args: list[str]) -> str:
    """The diff of one reader's context since `commit` (`_context_sides`),
    with the sections it reaches by links, as `_diff_text` gives it."""
    with _tree_at(commit) as tree:
        before, after = _context_sides(tree, commit, reader, args)
        return _diff_text([_text_diff(context_command(reader, args),
                                      before, after, tree, commit)])


def update_diff(context_commit: str, instructions_commit: str, reader: str,
                args: list[str]) -> str:
    """The diff of what a running reader holds: its context since
    `context_commit` (`_context_sides`), and the project instructions since
    `instructions_commit`, a side that has no such file as an empty text,
    with the sections each reaches by links, as `_diff_text` gives them. A
    chain from the project instructions starts at them. One tree serves
    two commits that are the same."""
    with ExitStack() as stack:
        context_tree = stack.enter_context(_tree_at(context_commit))
        instructions_tree = (context_tree if instructions_commit == context_commit
                             else stack.enter_context(_tree_at(instructions_commit)))
        before, after = _context_sides(context_tree, context_commit, reader, args)
        context = _text_diff(context_command(reader, args), before, after,
                             context_tree, context_commit)
        before, after = (_text_or_empty(root / PROJECT_INSTRUCTIONS)
                         for root in (instructions_tree, DOCUMENTS_ROOT))
        instructions = _text_diff(str(PROJECT_INSTRUCTIONS), before, after,
                                  instructions_tree, instructions_commit)
    start = LinkTarget(PROJECT_INSTRUCTIONS, "")
    instructions = replace(instructions, linked=[
        replace(c, chains=tuple((start, *chain) for chain in c.chains))
        for c in instructions.linked])
    return _diff_text([context, instructions])


def _text_or_empty(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _renders_in(tree: Path, commit: str,
                calls: list[tuple[str, list[str]]]) -> dict[str, str]:
    with ThreadPoolExecutor() as pool:
        befores = list(pool.map(lambda c: _render_in(tree, commit, *c), calls))
    return {context_command(*c): before for c, before in zip(calls, befores, strict=True)}


def _side_contexts(call: tuple[str, list[str]], then: dict[str, str],
                   now: bool) -> tuple[str, str]:
    """A reader's context at the commit and in the checkout, from `then`,
    the contexts of the readers the commit defines as `_renders_in` gives
    them, and `now`, whether the checkout defines the reader. A side that
    does not define the reader gives an empty context, and a reader neither
    side defines is a fault (`reader_named`)."""
    before = then.get(context_command(*call))
    after = context_text(reader_named(call[0]), call[1]) if now or before is None else ""
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
        calls += calls_of(name, form, [v for v in values.split(", ") if v])
    return calls


class ReaderChange(StrEnum):
    """How a change alters a reader's context: only the checkout defines
    the reader, only the commit does, both do and its contexts differ, or
    both do and only the text of a target it reaches by links differs
    (`linked_changes`)."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    LINKED = "linked"


def contexts_diff(commit: str) -> str:
    """Each reader, with its arguments, whose context the change since
    `commit` alters, or the text of a target it reaches by links, one per
    line, marked with its `ReaderChange` other than `CHANGED`, and after
    it, one indented line for each chain that leads to each target whose
    text the change alters, as `linked_changes` finds them
    (`LinkedChange.chain_lines`). A reader both sides define is altered
    where its context at `commit`, as `context_at` renders it in a detached
    worktree of `commit`, differs from its context in the checkout; a
    render at `commit` that fails is a fault, and a reader one side does
    not define is compared as `_side_contexts` gives its contexts.
    The checkout's readers come first, in `reader_calls` order, then the
    ones only the commit defines."""
    now = reader_calls()
    with _tree_at(commit) as tree:
        then = _calls_in(tree, commit)
        rendered = _renders_in(tree, commit, then)
        changes: list[tuple[tuple[str, list[str]], ReaderChange]] = [
            (c, ReaderChange.ADDED if c not in then else ReaderChange.CHANGED)
            for c in now]
        changes += [(c, ReaderChange.REMOVED) for c in then if c not in now]
        then_side, now_side = sides(tree, commit)
        out = []
        for (reader, args), change in changes:
            command = context_command(reader, args)
            before, after = _side_contexts((reader, args), rendered,
                                           change is not ReaderChange.REMOVED)
            linked = linked_changes(before, after, then_side, now_side)
            if change is ReaderChange.CHANGED and before == after:
                if not linked:
                    continue
                change = ReaderChange.LINKED
            mark = "" if change is ReaderChange.CHANGED else f" ({change})"
            out.append(f"{command}{mark}\n")
            out += [f"    {line}\n" for c in linked for line in c.chain_lines()]
    return "".join(out)
