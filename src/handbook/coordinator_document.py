"""The coordinator's document: the text that instructs the coordinator, the
session the user talks with, rendered from its source under
`prompts/agents/notes/` as an agent document is, into `.claude/coordinator.md`,
which is generated and not tracked.

The session-start hook gives the rendering to the coordinator at the
session's start, at a resume, after a `/clear` and after each compaction.
Claude Code fires that hook for each top-level session and for no subagent,
and it states the session's entry point in `CLAUDE_CODE_ENTRYPOINT`: the
hook gives the rendering to a session the user talks with, and nothing to a
`claude -p` session. A `claude -p` session keeps the entry point it inherits where that
is `claude-desktop`, so the hook also gives nothing to a session whose
process, `CLAUDE_PID`, was started with `-p` or `--print`. The hook's text
reaches the session whole only up to `HOOK_TEXT_CAP` characters, so a
longer rendering is a fault.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from engine import checkout
from handbook.agents import agent_dir
from handbook.context import entry_text
from handbook.contexts import marked_section
from handbook.generated import Rendering, write_generated
from handbook.paths import repo_label

COORDINATOR_DOC = agent_dir() / "notes" / "coordinator.md"
COORDINATOR_PATH = checkout.claude() / "coordinator.md"

HOOK_TEXT_CAP = 10_000
"""The most characters of a hook's text that Claude Code puts in the
session's context. Past it, the session gets a preview and the path of a
file that holds the text."""

ENTRY_POINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
SESSION_PID_ENV = "CLAUDE_PID"
PRINT_FLAGS = frozenset({"-p", "--print"})


class EntryPoint(StrEnum):
    """How a session was started, as Claude Code states it in
    `ENTRY_POINT_ENV`."""

    CLI = "cli"
    """An interactive session at a terminal."""
    DESKTOP = "claude-desktop"
    """A session in the desktop app."""
    PRINT = "sdk-cli"
    """A `claude -p` session."""


USER_ENTRY_POINTS = frozenset({EntryPoint.CLI, EntryPoint.DESKTOP})
"""The entry points of a session the user talks with."""


def coordinator_text(doc: Path = COORDINATOR_DOC) -> str:
    """The coordinator's document, rendered from `doc` as an entry document
    is (`entry_text`). A missing source, and a rendering longer than
    `HOOK_TEXT_CAP`, are faults."""
    if not doc.is_file():
        raise SystemExit("the coordinator's document has no source at "
                         f"{repo_label(doc)}")
    text = entry_text(doc)
    if len(text) > HOOK_TEXT_CAP:
        raise SystemExit(
            f"the coordinator's document, rendered from {repo_label(doc)}, holds "
            f"{len(text)} characters; the session-start hook gives a session "
            f"{HOOK_TEXT_CAP} at most")
    return text


def coordinator_context() -> str:
    """What reaches the coordinator from the session-start hook, as
    `session-start` gives it."""
    return marked_section(repo_label(COORDINATOR_PATH), coordinator_text())


def coordinator_rendering(path: Path = COORDINATOR_PATH,
                          doc: Path = COORDINATOR_DOC) -> Rendering:
    return Rendering(path, coordinator_text(doc))


def entry_point(env: Mapping[str, str]) -> EntryPoint:
    """The entry point `env` states. A missing one, and one no
    `EntryPoint` names, are faults."""
    value = env.get(ENTRY_POINT_ENV)
    if value is None:
        raise SystemExit(f"{ENTRY_POINT_ENV} is not set: the session-start "
                         "hook runs only under Claude Code")
    try:
        return EntryPoint(value)
    except ValueError:
        raise SystemExit(
            f"{ENTRY_POINT_ENV}={value} is no entry point the session-start "
            "hook knows; it knows " + ", ".join(e.value for e in EntryPoint)
        ) from None


def print_session(env: Mapping[str, str]) -> bool:
    """Whether the session's process, as `env` states it, was started with
    one of `PRINT_FLAGS`. `ps` gives the arguments joined by spaces, so an
    argument that holds a space and a flag as a word reads as that flag. A
    missing pid, and a process `ps` does not find, are faults."""
    pid = env.get(SESSION_PID_ENV)
    if pid is None:
        raise SystemExit(f"{SESSION_PID_ENV} is not set: the session-start "
                         "hook runs only under Claude Code")
    done = subprocess.run(["ps", "-ww", "-o", "args=", "-p", pid],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"ps finds no process {pid}, the session's "
                         f"{SESSION_PID_ENV}")
    return not PRINT_FLAGS.isdisjoint(done.stdout.split())


def session_start_text(env: Mapping[str, str], path: Path = COORDINATOR_PATH,
                       doc: Path = COORDINATOR_DOC) -> str:
    """What the session-start hook gives the session `env` describes: the
    coordinator's document, written to `path` first, for a session the user
    talks with, and nothing for a `claude -p` session. Claude Code puts a
    hook's output in the session's context only where the hook exits 0, so
    where the write fails, the hook gives the failure's text and then the
    rendering. That text does not count against `HOOK_TEXT_CAP`: past the
    cap, the session's preview opens with it, and the file Claude Code
    names holds the rest."""
    if entry_point(env) not in USER_ENTRY_POINTS or print_session(env):
        return ""
    rendering = coordinator_rendering(path, doc)
    try:
        write_generated([rendering])
    except (SystemExit, checkout.GitFailed) as e:
        return f"{_failure(e)}\n\n{rendering.text}"
    return rendering.text


def _failure(e: SystemExit | checkout.GitFailed) -> str:
    """The text of a failed write of the coordinator's document."""
    return str(e.code) if isinstance(e, SystemExit) else str(e)
