"""The readers the `context` command knows, and their contexts at a commit
and the diff of each since one."""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
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


def context_diff(commit: str, reader: str, args: list[str]) -> str:
    """The unified diff from one reader's context at `commit`, as
    `context_at` renders it in a detached worktree of `commit`, to its
    context in the checkout. Empty where the two are the same. A side that
    does not define the reader, as `contexts_diff` finds it, gives an empty
    context, so the diff of an added reader gains every line and that of a
    removed one loses every line. A reader neither side defines, and a
    render that fails, are faults."""
    call = (reader, args)
    with _tree_at(commit) as tree:
        then = call in _calls_in(tree, commit)
        before = _render_in(tree, commit, reader, args) if then else ""
    now = call in reader_calls()
    after = context_text(reader, args) if now or not then else ""
    head = _command(reader, args)
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"{head} at {commit}", tofile=head))


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


class ReaderChange(StrEnum):
    """How a change alters a reader's context: only the checkout defines
    the reader, only the commit does, or both do and its contexts
    differ."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


def contexts_diff(commit: str) -> str:
    """Each reader, with its arguments, whose context the change since
    `commit` alters, one per line, marked with its `ReaderChange` where
    only one side defines it. A reader both sides define is altered where
    its context at `commit`, as `context_at` renders it in a detached
    worktree of `commit`, differs from its context in the checkout; a
    render at `commit` that fails is a fault.
    The checkout's readers come first, in `reader_calls` order, then the
    ones only the commit defines."""
    now = reader_calls()
    with _tree_at(commit) as tree:
        then = _calls_in(tree, commit)
        both = [c for c in now if c in then]
        with ThreadPoolExecutor() as pool:
            befores = list(pool.map(lambda c: _render_in(tree, commit, *c), both))
    rendered = {_command(*c): before for c, before in zip(both, befores, strict=True)}
    changes = [(c, ReaderChange.ADDED if c not in then else ReaderChange.CHANGED)
               for c in now]
    changes += [(c, ReaderChange.REMOVED) for c in then if c not in now]
    out = []
    for (reader, args), change in changes:
        command = _command(reader, args)
        if change is ReaderChange.CHANGED:
            if rendered[command] != context_text(reader, args):
                out.append(f"{command}\n")
        else:
            out.append(f"{command} ({change})\n")
    return "".join(out)
