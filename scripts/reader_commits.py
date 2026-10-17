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
may hold its own context at, then the one for its project instructions; or,
for a subagent before its first update, one commit, the launch commit: its
tree's `HEAD` at its launch.
The coordinator's record is a file of its session directory named `main`,
and a subagent's is a file named by its agent id in the directory of the
project's sessions, so a resume in any session keeps the commits the
agent's run last had.

Where the session-start hook gives the coordinator's document, it writes
the `HEAD` of the checkout as both commits of the coordinator's record at a
`startup` or a `clear`, and at a `compact` or a `resume` only where the
coordinator has no record, since a summary or a restored conversation may
still hold documents from before. The SubagentStart hook writes a
subagent's record where it has none yet, at its launch (`start_agent`). A
subagent's own compaction, at which no `SessionStart` runs, leaves its
record as it stands.

At each call of a tool a PreToolUse hook covers, `reader_update` gives the
reader its update, and records `HEAD` as both commits once the hook's
output is printed. For a record of two commits, it compares them with its
tree's `HEAD`, and where both are the same it gives nothing. Otherwise it
gives the reader, under a head that says it may already hold some of the
changes and how to read them, the diff of its documents since its commits,
as `scripts/context.py context --update` prints it in the reader's tree,
or the failure of that run. That diff runs
for the context from the context's commit, for `CLAUDE.md` from the
instructions' commit, and for the sections links from `CLAUDE.md`
reach from the context's commit where it descends from the
instructions' commit, and from the instructions' commit otherwise. That run
is skipped where the context's commit is `HEAD`, `CLAUDE.md` does not
differ between the instructions' commit and `HEAD`, and no file of the
document set `[tool.controlled_markdown]` names differs between the linked
sections' commit and `HEAD`.

For a record of one commit, the held texts date the subagent's documents in
place of a commit, since the harness may give a subagent an agent
definition other than the one its tree holds at its launch. The held
context is the `systemPrompt[0]` of the first `prompt_snapshot` attachment
of the subagent's transcript, and the held `CLAUDE.md` the `content` of the
first entry of `type` `Project` whose `path` ends in `/CLAUDE.md` in the
`files` of its first `instructions` attachment: the texts the harness gave
it. The update gives, under a head that says so, the diff from those texts
and of each section their links reach from the launch commit, as
`scripts/context.py context --update --held` prints it in the reader's
tree, or the failure of that run. A transcript of a subagent whose type has
a document, that holds either text in no such form, is a fault, and its
record does not move.

A reader whose diff holds nothing, and a caller that is no reader, get
nothing, and the record moves all the same. A caller with no record, such
as a `claude -p` session, gets nothing, and so does a session started
before its session-start hook wrote one. A caller of unknown type is a
fault, and its record does not move.

The update holds a lock on the record while it runs, so of two calls of one
reader at once, the second waits for the first, and gives nothing once the
first has given the diff. A text longer than the hook text Claude Code puts
in a context whole (`handbook.coordinator_document.HOOK_TEXT_CAP`) reaches
the reader as a preview and the path of a file that holds it, and its head,
which stands in that preview, has the reader read that file whole.

A `context --update` run that succeeds is kept under `checkout.cache()`,
keyed by its arguments, the held texts it reads, its tree's `HEAD`, and the
path and content of each file `git status` lists in that tree, so that a
later update with the same key, of any reader in any session, gives the
kept output in place of a run. Of two updates with one key at once, the
second waits for the first's run and gives what it kept. A file git
ignores is not in the key."""

import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import IO, Any, NamedTuple

from hook_entry import Update

RECORDS = "reader-commits"
"""The directory of the records, in a session directory or in the
directory of the project's sessions."""

UPDATE_CACHE = "reader-updates"
"""The directory of the kept `context --update` runs under
`checkout.cache()`."""

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


def _commits(f: IO[str]) -> list[str]:
    """The one or two commits the record `f` holds, one per line. Any other
    text is a fault."""
    lines = f.read().split()
    if len(lines) not in (1, 2) or not all(COMMIT.fullmatch(c) for c in lines):
        raise ValueError(f"the record {f.name} holds `{' '.join(lines)}`, "
                         "not one or two commits")
    return lines


def _write(f: IO[str], *commits: str) -> None:
    f.seek(0)
    f.truncate()
    f.write("".join(f"{c}\n" for c in commits))
    f.flush()


def start_session(hook: dict[str, Any], coordinator: bool) -> None:
    """Where `coordinator`, record the `HEAD` of the checkout as both
    commits of the record of the coordinator of the session the
    `SessionStart` input `hook` names, at a `startup` or `clear` or where it
    has none. Any other source is a fault."""
    source = SessionSource(hook["source"])
    if coordinator:
        head = tree_head(hook)[1]
        with _locked(record_path(hook)) as f:
            if source in FRESH_SOURCES or not f.read().strip():
                _write(f, head, head)


def start_agent(hook: dict[str, Any]) -> None:
    """Record the launch commit of the subagent the `SubagentStart` input
    `hook` names, where it has no record."""
    with _locked(record_path(hook)) as f:
        if not f.read().strip():
            _write(f, tree_head(hook)[1])


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


class _Run(NamedTuple):
    """A `context --update` run."""

    command: str
    returncode: int
    stdout: str
    stderr: str


def _status_digest(h: "hashlib._Hash", tree: Path) -> None:
    """Adds to `h` the path and content of each file `git status` lists in
    `tree` as differing from its `HEAD` or untracked."""
    from engine import checkout
    from engine.memo import hash_file

    listed = checkout.git_out(tree, "status", "--porcelain=v1", "-z",
                              "--untracked-files=all", "--no-renames")
    for name in sorted(entry[3:] for entry in listed.split("\0") if entry):
        try:
            body: bytes | None = (tree / name).read_bytes()
        except OSError:
            body = None
        hash_file(h, name, body)


def _cached_run(tree: Path, after: str, args: list[str],
              held: tuple[str, str] | None = None) -> _Run:
    """The `context --update` run with `args` in `tree`, whose `HEAD` is
    `after`, as the module docstring gives the kept runs; with `held`, the
    texts the `--held` form reads from its two files."""
    import tempfile

    from engine import checkout
    from engine.memo import read_or_make
    from handbook.reader_diffs import CONTEXT_SCRIPT, PROJECT_INSTRUCTIONS

    h = hashlib.sha256()
    for part in [after, *args, *(held or ())]:
        h.update(part.encode() + b"\0")
    h.update(b"\1" if held else b"\0")
    _status_digest(h, tree)
    key = checkout.cache() / UPDATE_CACHE / h.hexdigest()

    def made() -> tuple[_Run, bool]:
        with tempfile.TemporaryDirectory() as tmp:
            files = [Path(tmp) / "context", Path(tmp) / PROJECT_INSTRUCTIONS]
            for file, text in zip(files, held or (), strict=False):
                file.write_text(text)
            argv = ["uv", "run", "python", str(CONTEXT_SCRIPT), "context", "--update",
                    *(["--held", *map(str, files)] if held else []), *args]
            done = subprocess.run(argv, cwd=tree, env=checkout.tree_env(),
                                  capture_output=True, text=True)
        run = _Run(" ".join(argv), done.returncode, done.stdout, done.stderr)
        return run, run.returncode == 0

    with _locked(key.with_suffix(".lock")):
        return read_or_make(key.with_suffix(".json"),
                            lambda data: _Run(*json.loads(data)),
                            lambda run: json.dumps(run).encode(), made)


def _run_update(done: _Run, fields: dict[str, Any],
                failed: str, head: str) -> str | None:
    """The text that gives a reader the output of `done`, a `context --update`
    run, under `head`; `failed`, then the stderr of the run, where
    it fails; or None where it prints nothing. `fields`, with the run's
    `command` and its exit `code`, fill both texts. `failed` goes on to the
    step that has the reader read its documents again, from the commit
    `fields` gives as `since`, in the place it gives as `where`."""
    from controlled_markdown import mctx
    from handbook.coordinator_document import HOOK_TEXT_CAP

    fields = {**fields, "command": done.command, "code": done.returncode}
    opening = mctx("Your working tree is at commit {after}, and your documents there may "
                   "differ from the ones you hold.")
    if done.returncode != 0:
        said = "\n".join([opening, failed, mctx(
            "Before you act by a document of yours, run `git diff --stat {since} {after}` "
            "{where}, and read again each file it lists that your context or "
            "`CLAUDE.md` holds or has you read.")]).format(**fields)
        print(f"{UPDATE}: {said}\n{done.stderr.strip()}", file=sys.stderr)
        return f"{said}\n\n{done.stderr.strip()}"
    if not done.stdout.strip():
        return None
    text = "\n".join([opening, head]).format(**fields) + "\n" + mctx("""
        - From now on, act by your context and `CLAUDE.md` as the diff leaves them: by its `+` lines, and no longer by its `-` lines.
        - After those two, the diff gives each section that links from them reach, each under a line that gives its path, then one line `<target> via <source>` for each link on the way.
            - In a line `<target> via <source>`, a line of `<source>` links to `<target>`, and `<source>` is `context` or `CLAUDE.md` where the link stands there.
        - Act by a section's `+` lines only where a path of those links, each of which has you read its target, runs from your context or `CLAUDE.md` to it, and not where a link only mentions it.
        """)
    if len(text) + len(done.stdout) > HOOK_TEXT_CAP:
        # Ticket 2-482: an agent took the harness's preview of a long output
        # for the whole output.
        text += "\n" + mctx(
            "This text is longer than Claude Code puts in your context whole, "
            "so you see a preview of it and the path of a file that holds it: "
            "read that file whole before you act.")
    return f"{text}\n\n{done.stdout}"


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
    from handbook.reader_diffs import PROJECT_INSTRUCTIONS, linked_commit

    if context == after and not (
            _documents_differ(tree, instructions, after, str(PROJECT_INSTRUCTIONS))
            or _documents_differ(tree, linked_commit(tree, context, instructions), after)):
        return None
    reader, args = call
    return _run_update(
        _cached_run(tree, after, [context, instructions, reader, *args]),
        {"after": after, "context": context, "instructions": instructions,
         "since": "<commit>",
         "where": mctx("in your working tree with each of those two commits")},
        "\n".join([
            mctx("Your own context may be at commit {context}, and the project "
                 "instructions, `CLAUDE.md`, at commit {instructions}."),
            mctx("The diff of your documents between those commits could not be "
                 "computed: `{command}` exited {code} and wrote what follows.")]),
        "\n".join([
            mctx("The diff below, which `{command}` prints, runs from the oldest commit "
                 "you may hold each of them at: your own context from commit {context}, "
                 "and the project instructions, `CLAUDE.md`, from commit {instructions}.")]))


SNAPSHOT = "prompt_snapshot"
"""The type of the transcript attachment that holds the system prompt the
harness gave a run."""

INSTRUCTIONS = "instructions"
"""The type of the transcript attachment that holds the instruction files
the harness gave a run."""


def held_texts(path: Path) -> tuple[str, str]:
    """The context and the `CLAUDE.md` the transcript at `path` holds as
    given to its run, as the module docstring gives them. A transcript that
    holds either in no such form is a fault."""
    from handbook.reader_diffs import PROJECT_INSTRUCTIONS
    from transcript_entries import entries_forward

    first: dict[str, dict[str, Any]] = {}
    for e in entries_forward(path):
        a = e.get("attachment") if e.get("type") == "attachment" else None
        if isinstance(a, dict) and a.get("type") in (SNAPSHOT, INSTRUCTIONS):
            first.setdefault(a["type"], a)
            if len(first) == 2:
                break
    prompt = first[SNAPSHOT].get("systemPrompt") if SNAPSHOT in first else None
    files = first[INSTRUCTIONS].get("files") if INSTRUCTIONS in first else None
    projects = [f.get("content") for f in files
                if isinstance(f, dict) and f.get("type") == "Project"
                and isinstance(f.get("path"), str) and f["path"].endswith(f"/{PROJECT_INSTRUCTIONS}")
                ] if isinstance(files, list) else []
    context = prompt[0] if isinstance(prompt, list) and prompt else None
    instructions = projects[0] if projects else None
    if not isinstance(context, str) or not isinstance(instructions, str):
        raise ValueError(f"the transcript {path} holds no context or no "
                         f"`CLAUDE.md` as given to its run, in a `{SNAPSHOT}` "
                         f"and an `{INSTRUCTIONS}` attachment")
    return context, instructions


def held_update_text(tree: Path, after: str, launch: str,
                     call: tuple[str, list[str]], held: tuple[str, str]) -> str | None:
    """The text that gives the reader `call` the diff of its context and its
    project instructions from `held`, the texts it was given at its launch,
    and of the sections they reach by links from `launch`, to `after`, the
    `HEAD` of `tree`, as `context --update --held` prints it in `tree`; the
    failure of that run; or None where the diff holds nothing."""
    from controlled_markdown import mctx

    reader, args = call
    return _run_update(
        _cached_run(tree, after, [launch, reader, *args], held),
        {"after": after, "launch": launch, "since": launch,
         "where": mctx("in your working tree")},
        "\n".join([
            mctx("Your own context and the project instructions, `CLAUDE.md`, are "
                 "the ones you were given at your launch, at commit {launch}."),
            mctx("The diff of your documents since then could not be computed: "
                 "`{command}` exited {code} and wrote what follows.")]),
        mctx("The diff below, which `{command}` prints, runs from the texts you were "
             "given at your launch for your own context and the project instructions, "
             "`CLAUDE.md`, and from commit {launch}, your tree's `HEAD` at your launch, "
             "for each section that links from them reach."))


def _update(text: str | None) -> Update | None:
    from controlled_markdown import mctx

    if text is None:
        return None
    return Update(text, mctx(
        "This call was not run, since your documents may have changed: the hook "
        "additional context of this call gives how. Make the call again only where "
        "your documents, as that context leaves them, still give it."))


@contextmanager
def reader_update(hook: dict[str, Any]) -> Iterator[Update | None]:
    """The update that gives the caller of the hook input `hook` the diff of
    its documents since its record, as the module docstring gives it, or
    None, held under the lock of its record. Where the block ends without
    an error, the record moves to the tree's `HEAD`. A record that holds no
    one or two commits is a fault."""
    try:
        f = record_path(hook).open("r+")
    except FileNotFoundError:
        yield None
        return
    with f:
        fcntl.flock(f, fcntl.LOCK_EX)
        commits = _commits(f)
        tree, after = tree_head(hook)
        if commits == [after, after]:
            yield None
            return
        call = reader_call(hook)
        if call is None:
            yield None
        elif len(commits) == 2:
            context, instructions = commits
            yield _update(update_text(tree, after, context, instructions, call))
        else:
            from run_reads import caller_transcript

            yield _update(held_update_text(tree, after, commits[0], call,
                                           held_texts(caller_transcript(hook))))
        _write(f, after, after)
