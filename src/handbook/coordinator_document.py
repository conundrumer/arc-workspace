"""The coordinator's document: the text that instructs the coordinator, the
session the user talks with, rendered from its source under
`prompts/agents/notes/` as an agent document is, into `.claude/coordinator.md`,
which is generated and not tracked.

The session-start hook gives the rendering to the coordinator at the
session's start, at a resume, after a `/clear` and after each compaction.
Claude Code fires that hook for each top-level session and for no subagent,
and it states the session's entry point in `CLAUDE_CODE_ENTRYPOINT`: the
hook gives the rendering to a session the user talks with, and nothing to a
`claude -p` session. A `claude -p` session takes `sdk-cli` where the entry
point it inherits is `cli`, and keeps any other, such as `claude-desktop`.
So a session whose entry point is `cli` is one the user talks with, and the
hook gives nothing to a session whose entry point is a kept one and whose
process, `CLAUDE_PID`, was started with `-p` or `--print`. A launcher can
request user-session instructions through `SESSION_INTERACTION_ENV`.
The hook's text reaches the session whole only up to `HOOK_TEXT_CAP` characters, so a
longer rendering is a fault.

The rendering's source gives its budget below that cap (`handbook.budget`).
Each command that renders the document for an editor or a reviewer checks
that budget: `context coordinator` and `context user-session` go through
`budgeted_text`, and `scripts/context.py --write` checks each budget
(`handbook.budgeted`). The session-start hook checks its rendering against
`HOOK_TEXT_CAP` alone, so a session starts with its document where an
older rendering passes the budget.

Where the user starts the coordinator with `claude`, its reader is
`coordinator`, and it reads the session-start hook's text alone
(`coordinator_context`). Where the user starts it with `scripts/claude.py`,
its reader is `user-session`, or the reader its `--reader` option names
(`APPENDIX_DOCS`), and it reads both texts: that script's appendix to the
system prompt (`coordinator_appendix`), then the session-start hook's text
(`user_session_context`). The appendix reaches
the session by `--append-system-prompt-file` and not by the hook, so
`HOOK_TEXT_CAP` does not bound it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.agent_documents import agent_dir
from handbook.budget import checked
from handbook.context import ARCLOG_SESSION_DOC, USER_SESSION_DOC, entry_text
from handbook.contexts import APPENDIX, marked_section
from handbook.generated import Rendering, write_generated
from handbook.paths import repo_label
from handbook.reader_names import ReaderName

COORDINATOR_DOC = agent_dir() / "notes" / "coordinator.md"
COORDINATOR_PATH = checkout.claude() / "coordinator.md"

HOOK_TEXT_CAP = 10_000
"""The most characters of a hook's text that Claude Code puts in the
session's context. Past it, the session gets a preview and the path of a
file that holds the text."""

ENTRY_POINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
SESSION_PID_ENV = "CLAUDE_PID"
PRINT_FLAGS = frozenset({"-p", "--print"})
SESSION_INTERACTION_ENV = "CLAUDE_CONFIG_SESSION_INTERACTION"
"""An explicit opt-in to user-session instructions, shared with the global
session-interaction hook. Its enabled value is `1`."""

SESSION_READER_ENV = "ARC_SESSION_READER"
"""The environment variable an entry point sets to the name of the reader
of the session it starts."""


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

KEPT_ENTRY_POINTS = USER_ENTRY_POINTS - {EntryPoint.CLI}
"""The entry points of a session the user talks with that a `claude -p`
session started under it keeps."""


def coordinator_text(doc: Path = COORDINATOR_DOC) -> str:
    """The coordinator's document, rendered from `doc` as an entry document
    is (`entry_text`). A missing source, and a rendering longer than
    `HOOK_TEXT_CAP`, are faults."""
    if not doc.is_file():
        raise SystemExit(mctx("the coordinator's document has no source at "
                              "{doc}").format(doc=repo_label(doc)))
    text = entry_text(doc)
    if len(text) > HOOK_TEXT_CAP:
        raise SystemExit(mctx(
            "the coordinator's document, rendered from {doc}, holds {size} "
            "characters; the session-start hook gives a session {cap} at "
            "most").format(doc=repo_label(doc), size=len(text), cap=HOOK_TEXT_CAP))
    return text


def budgeted_text(doc: Path = COORDINATOR_DOC) -> str:
    """`coordinator_text`, checked against the budget `doc` gives."""
    return checked(doc, coordinator_text(doc), COORDINATOR_PATH)


APPENDIX_DOCS = {ReaderName.USER_SESSION: USER_SESSION_DOC,
                 ReaderName.ARCLOG_SESSION: ARCLOG_SESSION_DOC}
"""The entry document of each reader that `scripts/claude.py` starts: the
document it appends to the coordinator's system prompt."""


def coordinator_appendix(reader: ReaderName = ReaderName.USER_SESSION) -> str:
    """The text `scripts/claude.py` appends to the system prompt of the
    coordinator whose reader is `reader`."""
    return entry_text(APPENDIX_DOCS[reader])


def coordinator_context() -> str:
    """What reaches the coordinator the user starts with `claude`: the
    session-start hook's text, as `session-start` gives it."""
    return marked_section(repo_label(COORDINATOR_PATH), budgeted_text())


def user_session_context(reader: ReaderName = ReaderName.USER_SESSION) -> str:
    """What reaches the coordinator the user starts with `scripts/claude.py`
    as the reader `reader`, in the order the session receives it: the
    system-prompt appendix that script gives, then the session-start hook's
    text."""
    return "\n".join([marked_section(APPENDIX, coordinator_appendix(reader)),
                      coordinator_context()])


def coordinator_rendering(path: Path = COORDINATOR_PATH,
                          doc: Path = COORDINATOR_DOC) -> Rendering:
    return Rendering(path, coordinator_text(doc))


def _claude_code_value(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None:
        raise SystemExit(mctx("{name} is not set: the session-start hook runs "
                              "only under Claude Code").format(name=name))
    return value


def entry_point(env: Mapping[str, str]) -> EntryPoint:
    """The entry point `env` states. A missing one, and one no
    `EntryPoint` names, are faults."""
    value = _claude_code_value(env, ENTRY_POINT_ENV)
    try:
        return EntryPoint(value)
    except ValueError:
        raise SystemExit(mctx(
            "{env}={value} is no entry point the session-start hook knows; it "
            "knows {known}").format(
                env=ENTRY_POINT_ENV, value=value,
                known=", ".join(e.value for e in EntryPoint))) from None


def print_session(env: Mapping[str, str]) -> bool:
    """Whether the session's process, as `env` states it, was started with
    one of `PRINT_FLAGS`. `ps` gives the arguments joined by spaces, so an
    argument that holds a space and a flag as a word reads as that flag.
    The hook asks this only of a session whose entry point is one of
    `KEPT_ENTRY_POINTS`, so a prompt the user gives as an argument of a
    `cli` session never reads as a flag. A missing pid, and a process `ps`
    does not find, are faults."""
    pid = _claude_code_value(env, SESSION_PID_ENV)
    done = subprocess.run(["ps", "-ww", "-o", "args=", "-p", pid],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(mctx("ps finds no process {pid}, the session's "
                              "{env}").format(pid=pid, env=SESSION_PID_ENV))
    return not PRINT_FLAGS.isdisjoint(done.stdout.split())


def session_start_text(env: Mapping[str, str], path: Path = COORDINATOR_PATH,
                       doc: Path = COORDINATOR_DOC) -> str:
    """What the session-start hook gives the session `env` describes: the
    coordinator's document, written to `path` first, for a session the user
    talks with, and nothing for a `claude -p` session: one whose entry
    point is none of `USER_ENTRY_POINTS`, or is one of `KEPT_ENTRY_POINTS`
    where `print_session` holds, unless `SESSION_INTERACTION_ENV` is `1`.
    Claude Code puts a
    hook's output in the session's context only where the hook exits 0, so
    where the write fails, the hook gives the failure's text and then the
    rendering. That text does not count against `HOOK_TEXT_CAP`: past the
    cap, the session's preview opens with it, and the file Claude Code
    names holds the rest."""
    point = entry_point(env)
    opted_in = env.get(SESSION_INTERACTION_ENV) == "1"
    if not opted_in and (point not in USER_ENTRY_POINTS or (
            point in KEPT_ENTRY_POINTS and print_session(env))):
        return ""
    rendering = Rendering(path, coordinator_text(doc))
    try:
        write_generated([rendering])
    except (SystemExit, checkout.GitFailed) as e:
        return f"{_failure(e)}\n\n{rendering.text}"
    return rendering.text


def _failure(e: SystemExit | checkout.GitFailed) -> str:
    """The text of a failed write of the coordinator's document."""
    return str(e.code) if isinstance(e, SystemExit) else str(e)
