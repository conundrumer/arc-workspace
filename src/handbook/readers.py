"""The readers the `context` command knows, and each reader's context in
the checkout."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from handbook.agents import agent_dir, agent_names
from handbook.context import role_dir, role_stems, workflow_dir, workflow_names
from handbook.contexts import (agent_context, codex_context, console_context,
                               console_stages, role_context, session_context,
                               survey_context, workflow_context)
from handbook.coordinator_document import coordinator_context, user_session_context
from handbook.fragments import fragment_parts, fragments_context
from handbook.paths import DOCUMENTS_ROOT
from handbook.reader_names import ReaderName


class ArgumentForm(StrEnum):
    """The argument a reader of the `context` command takes, as its usage
    line writes it."""

    NAME = "<name>"
    STAGE = "<stage>"
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


def _console_stages(root: Path) -> list[str]:
    """The console's stages, which `console_stages` lists only under
    `DOCUMENTS_ROOT`: another root is a fault."""
    if root != DOCUMENTS_ROOT:
        raise ValueError(f"the console's stages are listed under {DOCUMENTS_ROOT} alone, "
                         f"not under {root}")
    return console_stages()


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
    ReaderName.CONSOLE: Reader(ArgumentForm.STAGE, _console_stages,
                               lambda a: console_context(a[0])),
    ReaderName.SURVEY: Reader(None, _no_values, lambda _a: survey_context()),
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
        raise SystemExit("no reader named "
                         f"`{name}`\n{contexts_text()}".rstrip())
    return ReaderName(name)


def context_text(reader: ReaderName, args: list[str]) -> str:
    """One reader's whole context, in the order it arrives."""
    known = CONTEXT_READERS[reader]
    form = known.form
    if len(args) != (1 if form else 0):
        raise SystemExit(f"usage: {_usage(reader, form)}")
    return known.context(args)
