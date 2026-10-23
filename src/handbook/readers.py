"""The readers the `context` command knows, and each reader's context in
the checkout."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from handbook.agent_documents import agent_dir
from handbook.agents import agent_names
from handbook.context import role_dir, role_stems, workflow_dir, workflow_names
from handbook.contexts import (agent_context, codex_context, role_context,
                               session_context, workflow_context)
from handbook.coordinator_document import coordinator_context, user_session_context
from handbook.fragments import fragment_parts, fragments_context
from handbook.paths import DOCUMENTS_ROOT
from handbook.reader_names import ReaderName


class ArgumentForm(StrEnum):
    """The argument a reader of the `context` command takes, as its usage
    line writes it."""

    NAME = "<name>"
    PART = "<part>"


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


CONTEXT_READERS = {
    ReaderName.COORDINATOR: Reader(None, _no_values,
                                   lambda _a: coordinator_context()),
    ReaderName.USER_SESSION: Reader(None, _no_values,
                                    lambda _a: user_session_context()),
    ReaderName.SESSION: Reader(None, _no_values, lambda _a: session_context()),
    ReaderName.CODEX: Reader(None, _no_values, lambda _a: codex_context()),
    ReaderName.AGENT: Reader(ArgumentForm.NAME,
                             lambda r: agent_names(agent_dir(r)),
                             lambda a: agent_context(a[0])),
    ReaderName.ROLE: Reader(ArgumentForm.NAME, lambda r: role_stems(role_dir(r)),
                            lambda a: role_context(a[0])),
    ReaderName.WORKFLOW: Reader(ArgumentForm.NAME,
                                lambda r: workflow_names(workflow_dir(r)),
                                lambda a: workflow_context(a[0])),
    ReaderName.FRAGMENTS: Reader(ArgumentForm.PART, fragment_parts,
                                 lambda a: fragments_context(a[0])),
}
"""Each reader the `context` command knows, by name."""


def calls_of[N: str](name: N, form: str | None,
                     values: list[str]) -> list[tuple[N, list[str]]]:
    return [(name, [v]) for v in values] if form else [(name, [])]


def reader_calls() -> list[tuple[ReaderName, list[str]]]:
    """Each reader the `context` command knows, with each argument list it
    takes."""
    return [call for name, reader in CONTEXT_READERS.items()
            for call in calls_of(name, reader.form, reader.values(DOCUMENTS_ROOT))]


def context_command(reader: str, args: list[str]) -> str:
    """The `context` command line that prints one reader's context. The
    reader may be one that only a commit's code knows (`reader_diffs`)."""
    return " ".join(["context", reader, *args])


def _usage(reader: ReaderName, form: ArgumentForm | None) -> str:
    return context_command(reader, [form] if form else [])


def contexts_text() -> str:
    """Every reader the `context` command knows, one per line: its name, its
    argument form, and the values that argument takes."""
    out = []
    for name, reader in CONTEXT_READERS.items():
        head = _usage(name, reader.form)
        names = reader.values(DOCUMENTS_ROOT)
        out.append(f"{f"{head} ":<24}{', '.join(names)}".rstrip())
    return "\n".join(out) + "\n"


def reader_named(name: str) -> ReaderName:
    if name not in CONTEXT_READERS:
        raise SystemExit((mctx("no reader named `{name}`").format(name=name)
                          + "\n" + contexts_text()).rstrip())
    return ReaderName(name)


def context_text(reader: ReaderName, args: list[str]) -> str:
    """One reader's whole context, in the order it arrives."""
    known = CONTEXT_READERS[reader]
    form = known.form
    if len(args) != (1 if form else 0):
        raise SystemExit(mctx("usage: {usage}").format(usage=_usage(reader, form)))
    return known.context(args)
