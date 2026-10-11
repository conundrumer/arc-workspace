"""The commits whose documents each running reader last had, and the update
that gives a reader the diff of its documents since those commits.

A reader is the coordinator, the session the user talks with, or a
subagent whose type has a document under `prompts/agents/`. The
coordinator's reader is the one its entry point names in its environment
(`handbook.coordinator_document.SESSION_READER_ENV`), and `coordinator`
where it names none. Its documents
are its own context, as `scripts/context.py context` prints it, and the
project instructions, `CLAUDE.md` with the sections its links lead to,
which Claude Code gives each session and subagent beside its context. Its
tree is the checkout the hooks run from for the main session, and for a
subagent the tree its working directory stands in, so a subagent in a
worktree of its own has its branch's documents, and a merge to `master`
changes them only where its branch moves.

A reader's record holds two commits, one line each: the oldest commit it
may hold its own context at, then the one for its project instructions.
The coordinator's record is a file of its session directory named `main`,
and a subagent's is a file named by its agent id in the directory of the
project's sessions, so a resume in any session keeps the commits the
agent's run last had. The session's record, a file of its session
directory named `session`, holds one commit: the one at which Claude Code
last loaded the project instructions it gives the session's subagents.

The session-start hook writes, at each `SessionStart` of any source, the
`HEAD` of the checkout as the session's record. Where it gives the
coordinator's document, it writes that `HEAD` as both commits of the
coordinator's record at a `startup` or a `clear`, and at a `compact` or a
`resume` only where the coordinator has no record, since a summary or a
restored conversation may still hold documents from before. The
SubagentStart hook writes a subagent's record where it has none yet, at its
launch (`start_agent`): its context's commit is the session's
agent-definition commit, where the `HEAD` of its tree descends from it, and
its tree's `HEAD` otherwise. The session's agent-definition commit is the
one `master` stood at, by its reflog, at the time of the first line with a
timestamp in the session's main transcript, the time of its `startup`,
since the harness may give a subagent the agent file it loaded then. No
record holds it: it is read from the transcript at each launch, so a
`compact`, a `clear` and a `resume` leave it as it stands. A transcript
with no timestamp, and a reflog that does not reach back to that time, are
faults. Its
instructions' commit is the session's record; a session that has none is a
fault, and its subagents get no record. A subagent's own compaction, at
which no `SessionStart` runs, leaves its record as it stands.

At each call of a tool a PreToolUse hook covers, `reader_update` compares
the reader's commits with its tree's `HEAD`, and where both are the same it
gives nothing. Otherwise it gives the reader, under a head that says it may
already hold some of the changes and how to read them, the diff of its
documents since its commits, as `scripts/context.py context --update`
prints it in the reader's tree, or the failure of that run, and records
`HEAD` as both commits once the hook's output is printed. That diff runs
for the context from the context's commit, for `CLAUDE.md` from the
instructions' commit, and for the sections links from `CLAUDE.md`
reach from the context's commit where it descends from the
instructions' commit, and from the instructions' commit otherwise. That run
is skipped where the context's commit is `HEAD`, `CLAUDE.md` does not
differ between the instructions' commit and `HEAD`, and no file of the
document set `[tool.controlled_markdown]` names differs between the linked
sections' commit and `HEAD`. A reader whose diff holds nothing, and a caller that is no reader, get
nothing, and the record moves all the same. A caller with no record, such
as a `claude -p` session, gets nothing, and so does a session started
before its session-start hook wrote one. A caller of unknown type is a
fault, and its record does not move.

The update holds a lock on the record while it runs, so of two calls of one
reader at once, the second waits for the first, and gives nothing once the
first has given the diff. A text longer than the hook text Claude Code puts
in a context whole (`handbook.coordinator_document.HOOK_TEXT_CAP`) reaches
the reader as a preview and the path of a file that holds it, and its head,
which stands in that preview, has the reader read that file whole."""

import fcntl
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import IO, Any

RECORDS = "reader-commits"
"""The directory of the records, in a session directory or in the
directory of the project's sessions."""

SESSION = "session"
"""The name of the session's record."""

COMMIT = re.compile(r"[0-9a-f]{40}")

RECORD_FAILED = "recorded no commit"
"""The failure text of a start hook whose record fails."""

class SessionSource(StrEnum):
    """The `source` of a `SessionStart` hook input."""

    STARTUP = "startup"
    CLEAR = "clear"
    COMPACT = "compact"
    RESUME = "resume"


FRESH_SOURCES = {SessionSource.STARTUP, SessionSource.CLEAR}
"""The sources that start the coordinator's context anew. After any other,
it may still hold documents from before, in a summary or a restored
conversation."""

UPDATE = "reader_update"
"""The name a failed diff run is said under on stderr."""


def _records(hook: dict[str, Any]) -> Path:
    from run_reads import hook_session

    return hook_session(hook) / RECORDS


def record_path(hook: dict[str, Any]) -> Path:
    """The record of the caller of the hook input `hook`."""
    from run_reads import MAIN, caller_id

    agent = caller_id(hook)
    if agent is None:
        return _records(hook) / MAIN
    return _records(hook).parent.parent / RECORDS / agent


def reader_tree(hook: dict[str, Any]) -> Path:
    """The tree of the caller of the hook input `hook`: the checkout of the
    hooks for the main session, and for a subagent the tree its working
    directory stands in."""
    from engine import checkout
    from run_reads import caller_id

    return checkout.ROOT if caller_id(hook) is None else Path(hook["cwd"])


def tree_head(hook: dict[str, Any]) -> tuple[Path, str]:
    """The root of the caller's tree (`reader_tree`) and its `HEAD`."""
    from engine import checkout

    root, head = checkout.git_out(reader_tree(hook), "rev-parse",
                                  "--show-toplevel", "HEAD").split()
    return Path(root), head


@contextmanager
def _locked(path: Path) -> Iterator[IO[str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        yield f


def _commits(f: IO[str], count: int) -> list[str]:
    """The `count` commits the record `f` holds, one per line. Any other
    text is a fault."""
    lines = f.read().split()
    if len(lines) != count or not all(COMMIT.fullmatch(c) for c in lines):
        raise ValueError(f"the record {f.name} holds `{' '.join(lines)}`, "
                         f"not {count} commits")
    return lines


def _write(f: IO[str], *commits: str) -> None:
    f.seek(0)
    f.truncate()
    f.write("".join(f"{c}\n" for c in commits))
    f.flush()


def start_session(hook: dict[str, Any], coordinator: bool) -> None:
    """Record the `HEAD` of the checkout as the record of the session the
    `SessionStart` input `hook` names, and, where `coordinator`, as both
    commits of the coordinator's record, at a `startup` or `clear` or where
    it has none. Any other source is a fault."""
    source = SessionSource(hook["source"])
    head = tree_head(hook)[1]
    with _locked(_records(hook) / SESSION) as f:
        _write(f, head)
    if coordinator:
        with _locked(record_path(hook)) as f:
            if source in FRESH_SOURCES or not f.read().strip():
                _write(f, head, head)


def _startup_commit(hook: dict[str, Any], tree: Path) -> str:
    """The session's agent-definition commit, as the module docstring gives
    it, resolved in `tree`."""
    from datetime import datetime, timezone

    from agent_turns import first_time
    from engine import checkout
    from merge_change import MASTER
    from run_reads import hook_session, main_transcript

    transcript = main_transcript(hook_session(hook))
    started = first_time(transcript)
    if started is None:
        raise ValueError(f"the transcript {transcript} has no timestamp, so "
                         "the session's agent-definition commit is unknown")
    when = datetime.fromtimestamp(started, timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")
    argv = ("rev-parse", "--verify", f"{MASTER}@{{{when}}}")
    done = checkout.git(tree, *argv)
    if done.returncode != 0 or "only goes back to" in done.stderr:
        raise checkout.GitFailed(tree, argv, done.stderr)
    return done.stdout.strip()


def start_agent(hook: dict[str, Any]) -> None:
    """Record the commits of the subagent the `SubagentStart` input `hook`
    names, where it has no record. A session with no record is a fault."""
    with _locked(record_path(hook)) as f:
        if f.read().strip():
            return
        from handbook.reader_diffs import descends

        tree, head = tree_head(hook)
        startup = _startup_commit(hook, tree)
        context = startup if descends(tree, head, startup) else head
        session = _records(hook) / SESSION
        if not session.exists():
            raise FileNotFoundError(f"the session has no record {session}, so "
                                    "the commit of its project instructions is unknown")
        with _locked(session) as g:
            [instructions] = _commits(g, 1)
        _write(f, context, instructions)


def reader_call(hook: dict[str, Any]) -> tuple[str, list[str]] | None:
    """The reader of the `context` command whose context the caller of the
    hook input `hook` has, with its arguments, or None where the caller is
    a subagent whose type has no document. A caller of unknown type, and a
    reader name in `SESSION_READER_ENV` that no `ReaderName` gives, are
    faults."""
    from handbook.agents import agent_names
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
    return (ReaderName.AGENT, [kind]) if kind in agent_names() else None


def _documents_differ(tree: Path, before: str, after: str,
                      *paths: str) -> bool:
    """Whether a file of `paths`, or of the document set
    `[tool.controlled_markdown]` in `tree` names where none is given,
    differs between `before` and `after`."""
    from controlled_markdown.__main__ import configured
    from engine import checkout

    return checkout.git_answer(tree, "diff", "--quiet", before, after, "--",
                               *(paths or configured(tree))).returncode == 1


def update_text(tree: Path, after: str, context: str, instructions: str,
                call: tuple[str, list[str]]) -> str | None:
    """The text that gives the reader `call` the diff of its context from
    `context`, of its project instructions from `instructions`, and of the
    sections they reach by links from the commits `context --update` gives
    them, to `after`, the `HEAD` of `tree`, as `context --update` prints it
    in `tree`; the failure of that run; or None where the diff holds
    nothing, or where the context's commit is `after` and neither the
    project instructions since `instructions` nor a file of the document
    set since the linked sections' commit (`linked_commit`) differs from
    it."""
    from controlled_markdown import mctx
    from engine import checkout
    from handbook.coordinator_document import HOOK_TEXT_CAP
    from handbook.reader_diffs import CONTEXT_SCRIPT, PROJECT_INSTRUCTIONS, linked_commit

    if context == after and not (
            _documents_differ(tree, instructions, after, str(PROJECT_INSTRUCTIONS))
            or _documents_differ(tree, linked_commit(tree, context, instructions), after)):
        return None
    reader, args = call
    argv = ["uv", "run", "python", str(CONTEXT_SCRIPT), "context", "--update",
            context, instructions, reader, *args]
    done = subprocess.run(argv, cwd=tree, env=checkout.tree_env(),
                          capture_output=True, text=True)
    fields = {"after": after, "context": context, "instructions": instructions,
              "command": " ".join(argv),
              "opening": mctx(
                  "Your working tree is at commit {after}, and your documents "
                  "there may differ from the ones you hold").format(after=after)}
    if done.returncode != 0:
        failed = mctx(
            "{opening}: your own context may be at commit {context}, and the "
            "project instructions, `CLAUDE.md`, at commit {instructions}. The "
            "diff of your documents between those commits could not be "
            "computed: `{command}` exited {code} and wrote what follows. Before you act by a document of yours, run "
            "`git diff --stat <commit> {after}` in your working tree with each "
            "of those two commits, and read again each file it lists that your "
            "context or `CLAUDE.md` holds or has you read."
        ).format(**fields, code=done.returncode)
        print(f"{UPDATE}: {failed}\n{done.stderr.strip()}", file=sys.stderr)
        return f"{failed}\n\n{done.stderr.strip()}"
    if not done.stdout.strip():
        return None
    head = mctx(
        "{opening}. The diff below, which `{command}` prints, runs from the "
        "oldest commit you may hold each of them at: "
        "your own context from commit {context}, and the project instructions, "
        "`CLAUDE.md`, from commit {instructions}. So you may already hold some "
        "of its changes. From now on, act by your context and `CLAUDE.md` as "
        "the diff leaves them: by its `+` lines, and no longer by its `-` "
        "lines. After those two, the diff gives each section that links from "
        "them reach, each under a line that names it, a section that lies "
        "within another section or document the diff gives only within that "
        "one's diff, then one line `<target> via <source>` for each link on "
        "the way: a line of `<source>` links to `<target>`, and `<source>` is "
        "`context` or `CLAUDE.md` where the link stands there. Each `@@` line "
        "ends in the headings that hold the first line of its hunk, outermost "
        "first. Act by a section's `+` lines only where a path of those links, "
        "each of which has you read its target, runs from your context or "
        "`CLAUDE.md` to it, and not where a link only names it."
    ).format(**fields)
    if len(head) + len(done.stdout) > HOOK_TEXT_CAP:
        head += " " + mctx(
            "This text is longer than Claude Code puts in your context whole, "
            "so you see a preview of it and the path of a file that holds it: "
            "read that file whole before you act.")
    return f"{head}\n\n{done.stdout}"


@contextmanager
def reader_update(hook: dict[str, Any]) -> Iterator[str | None]:
    """The text that gives the caller of the hook input `hook` the diff of
    its documents since its recorded commits, or None, held under the lock
    of its record. Where the block ends without an error, the record moves
    to the tree's `HEAD`. A record that holds no two commits is a fault."""
    try:
        f = record_path(hook).open("r+")
    except FileNotFoundError:
        yield None
        return
    with f:
        fcntl.flock(f, fcntl.LOCK_EX)
        context, instructions = _commits(f, 2)
        tree, after = tree_head(hook)
        if context == instructions == after:
            yield None
            return
        call = reader_call(hook)
        yield None if call is None else update_text(tree, after, context,
                                                    instructions, call)
        _write(f, after, after)
