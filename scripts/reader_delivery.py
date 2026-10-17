"""The update a hook gives a reader, as `reader_commits` defines both, at
each call of a tool, with each prompt of the user and with each task
notification, and the time of its last delivery at a call.

Before and after each call of a tool, and with each prompt of the user and
each task notification, `reader_update` gives the reader its update, and
records `HEAD` as both commits once the hook's output is printed. For a
record of two commits, it compares them with its tree's `HEAD`, and where
both are the same it gives nothing. Otherwise it gives the reader, under a
head that says it may already hold some of the changes and how to read
them, the diff of its documents since its commits, as
`scripts/context.py context --update` prints it in the reader's tree, or
the failure of that run. That diff runs for the context from the context's
commit, for `CLAUDE.md` from the instructions' commit, and for the sections
links from `CLAUDE.md` reach from the context's commit where it descends
from the instructions' commit, and from the instructions' commit otherwise.
That run is skipped where the context's commit is `HEAD`, `CLAUDE.md` does
not differ between the instructions' commit and `HEAD`, and no file of the
document set `[tool.controlled_markdown]` names differs between the linked
sections' commit and `HEAD`.

For a launch record with a digest, the update reads the subagent's held
texts, as `reader_commits` gives them. Where their digest is the record's,
the update is that of a record that holds the launch commit twice;
otherwise it is that of a launch record with no digest, which gives the
diff from those texts (`reader_commits.held_update_text`).

A reader whose diff holds nothing, and a caller that is no reader, get
nothing, and the record moves all the same. A caller with no record, such
as a `claude -p` session, gets nothing, and so does a session started
before its session-start hook wrote one. A caller of unknown type is a
fault, and its record does not move.

The update holds a lock on the record while it runs, so of two calls of one
reader at once, the second waits for the first, and gives nothing once the
first has given the diff.

A delivery at a call, at PreToolUse, PostToolUse or PostToolUseFailure,
records its time as the modification time of the caller's delivery file
(`delivery_path`), once the output is printed; a delivery with a prompt
records none. A denial with no text is a delivery too, so a call after a
denied one is measured from that denial. Claude Code puts a delivery with a
call's result in the caller's context only after the calls the caller
chose in the same message as that call, and starts the next of those calls
within a fraction of a second, while a call of a later message starts at
least a model turn after. So at PreToolUse, where that file is younger than
`DELIVERY_BOUND` at the time the hook's entry started
(`hook_entry.STARTED`), before its check, the update denies the call, with
`_same_message_denial`, which holds no text, before any other step; where
it is older, the update removes it and goes on as above."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Any

from hook_entry import STARTED, Update
from reader_commits import (LaunchRecord, ReadRecord, Record, held_texts, held_update_text,
                            read_record, record_path, texts_digest, tree_head, type_reader,
                            update_text, write_record)


class HookEvent(StrEnum):
    """The `hook_event_name` of a hook input `reader_update` reads."""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"


CALL_EVENTS = {HookEvent.PRE_TOOL_USE, HookEvent.POST_TOOL_USE,
               HookEvent.POST_TOOL_USE_FAILURE}
"""The events of a call, whose delivery records its time."""

DELIVERED = ".delivered"
"""The suffix that `delivery_path` adds to the name of the record, which
`scripts/reader_update_hook.sh` adds as well."""

DELIVERY_BOUND = 0.5
"""In seconds. Of 23,547 first calls of a new message after a call's result,
none started within it (change 11-303)."""


def delivery_path(hook: dict[str, Any]) -> Path:
    """The delivery file of the caller of the hook input `hook`, beside its
    record."""
    path = record_path(hook)
    return path.with_name(path.name + DELIVERED)


def reader_call(hook: dict[str, Any]) -> tuple[str, list[str]] | None:
    """The reader of the `context` command whose context the caller of the
    hook input `hook` has, with its arguments, or None where the caller is
    a subagent whose type has no document. A caller of unknown type, and a
    reader name in `SESSION_READER_ENV` that no `ReaderName` gives, are
    faults."""
    from handbook.coordinator_document import SESSION_READER_ENV
    from handbook.reader_names import ReaderName
    from run_reads import MAIN, UNKNOWN_TYPE, agent_type, caller_transcript

    path = caller_transcript(hook)
    kind = agent_type(path)
    if kind is None:
        raise ValueError(UNKNOWN_TYPE.format(path=path))
    if kind == MAIN:
        name = os.environ.get(SESSION_READER_ENV)
        return (ReaderName.COORDINATOR if name is None else ReaderName(name)), []
    return type_reader(kind)


def _denial(text: str, where: str) -> Update:
    """The update `text`, with the reason that points the caller to the hook
    additional context of `where`."""
    from controlled_markdown import mctx

    return Update(text, mctx(
        "This call was not run, since your documents may have changed: the hook "
        "additional context of {where} gives how. Make the call again only where "
        "your documents, as that context leaves them, still give it.").format(where=where))


def _update(text: str | None) -> Update | None:
    from controlled_markdown import mctx

    return None if text is None else _denial(text, mctx("this call"))


def _same_message_denial() -> Update:
    from controlled_markdown import mctx

    return _denial("", mctx("an earlier call's result"))


def _delivered_lately(path: Path) -> bool:
    """Whether the delivery file `path` is younger than `DELIVERY_BOUND` at
    `STARTED`. An older one is removed."""
    try:
        age = STARTED - path.stat().st_mtime
    except FileNotFoundError:
        return False
    if age < DELIVERY_BOUND:
        return True
    path.unlink()
    return False


@contextmanager
def reader_update(hook: dict[str, Any]) -> Iterator[Update | None]:
    """The update that gives the caller of the hook input `hook` the diff of
    its documents since its record, or the denial of a call that starts
    within `DELIVERY_BOUND` of a delivery, as the module docstring gives
    them, or None, held under the lock of its record. Where the block ends
    without an error, the record moves to the tree's `HEAD`, and a delivery
    at a call records its time. An event other than a
    `HookEvent`, and a record that `read_record` does not read, are
    faults."""
    event = HookEvent(hook["hook_event_name"])
    delivered = delivery_path(hook)
    try:
        f = record_path(hook).open("r+")
    except FileNotFoundError:
        yield None
        return
    with f:
        fcntl.flock(f, fcntl.LOCK_EX)
        given: Update | None
        if event is HookEvent.PRE_TOOL_USE and _delivered_lately(delivered):
            given = _same_message_denial()
            yield given
        else:
            record = read_record(f)
            tree, after = tree_head(hook)
            if record == ReadRecord(after, after):
                yield None
                return
            call = reader_call(hook)
            given = None if call is None else _update(
                _record_update(hook, record, tree, after, call))
            yield given
            write_record(f, ReadRecord(after, after))
        if given is not None and event in CALL_EVENTS:
            delivered.touch()


def _record_update(hook: dict[str, Any], record: Record, tree: Path, after: str,
                   call: tuple[str, list[str]]) -> str | None:
    """The text of `reader_update` for `record`, as the module docstring
    gives it."""
    from run_reads import caller_transcript

    match record:
        case ReadRecord(context, instructions):
            return update_text(tree, after, context, instructions, call)
        case LaunchRecord(launch, predicted):
            held = held_texts(caller_transcript(hook))
            if predicted == texts_digest(held):
                return update_text(tree, after, launch, launch, call)
            return held_update_text(tree, after, launch, call, held)
