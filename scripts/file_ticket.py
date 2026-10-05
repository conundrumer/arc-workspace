"""File a ticket under the main tree's `tickets/`, from the main tree or any
worktree of it, print a ticket's path, and make a ticket's transitions and
write its log lines. `HELP`, which `--help` prints, says how an agent calls it."""

import fcntl
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from arc.task import task_file
from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and `transcripts` imports from there.
importable(checkout.scripts())

from transcripts import Refused, find, forked_from  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/file_ticket.py <domain> <subject> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>{defect_sections}
        EOF
        ```
    - A `change` takes this form on stdin in place of the one above, and may leave out `depends-on` and `priority`:
        ```
        ---
        kind: change
        depends-on: <number>, <number>
        priority: <0 to 100>
        ---
        # <title>{change_sections}
        EOF
        ```
    - `<domain>` is one of {domains}, and `<subject>` is the id of the thing it names: a task id for `task`, a ticket's number for `change` and `ticket`, a commit hash for `commit`, an agent id for `agent`. A `change` takes `change` as `<domain>` and `<namespace>-<short-title>` as `<subject>`, and each `_` in that `<subject>`, as in a namespace name such as `run_dl`, becomes `-`.
    - `<agent>` is your agent's name, which may end in `-<suffix>`. The command refuses a kind your agent may not file, and names the kinds it may.
    - A ticket's number is `<session>-<n>`: `<session>` is the index of the session that filed it, and `<n>` counts that session's tickets from 1. A ticket filed before a number gave the filing session's index has a bare number, and the command takes either form wherever it takes a number.
    - Numbers order with every bare number before every `<session>-<n>` number. Bare numbers compare as integers, and `<session>-<n>` numbers compare by `<session>`, then by `<n>`, each as an integer.
    - The session that files is the one whose id the filing agent's shell holds in `{session_var}`, in a subagent as in the main session. The command refuses a filing where the shell holds none.
    - A session's index has a file under `tickets/{sessions}/`, named by the index, that holds the session's id. A session forked from another takes the index of the session it was forked from, and the file then holds both ids, one per line.
    - `uv run python scripts/file_ticket.py index` prints the index of your session.
    - The command reserves the ticket's number, names the ticket `<number>_<domain>_<subject>_<agent>.md`, writes it under `tickets/draft/` for a `change` and `tickets/open/` for any other kind in the main tree, with the filing time in the first line of its `## Log`, and prints the path it wrote.
    - Run from a worktree, the command files with the main tree's copy of `scripts/file_ticket.py`, and refuses where the main tree has none.
    - Each `<number>` in `depends-on` is the number of a ticket the ticket tracker holds.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    - `uv run python scripts/file_ticket.py path <number>` prints the path of the ticket with that number, in whichever status it stands. It takes the name of a ticket filed before tickets had numbers in place of `<number>` too.
    - `uv run python scripts/file_ticket.py log <number> <status> <agent> --from <current status> [--id <agent id>] [<note>]` makes a transition of the ticket with that number and writes its log line, or writes a log line that moves nothing, and prints the ticket's path:
        - `<status>` and `<current status>` are each one of {statuses}. `<current status>` is the status you saw the ticket in.
        - The command refuses, and neither moves nor writes, where the ticket stands in another status than `<current status>`, or where its file moves before the command moves it.
        - Where `<status>` differs from `<current status>`, the command moves the ticket's file to the directory of `<status>`.
        - The command appends `<time> <status> [<agent>]: <note>` to the file's `{log}`, with the time in UTC in the form `{time_form}`, and with `<agent> <agent id>` in the bracket where `--id` gives an agent id. A line with no `<note>` ends at the bracket.
        - An `assigned` line takes, in `--id`, the agent id of the agent that writes it.
        - On a ticket that already stands in `assigned`, the command refuses an `assigned` line unless its `--id` holds the ticket. The holder is the agent id of the last `assigned` line that gives one, in its bracket or as the first word of its note, among the log's final run of `assigned` lines. Where none of them gives one, the ticket has no holder.
        - The note of a line that moves a ticket into `{blocked}` opens with what the ticket waits on: `{user}`, or `{change} <number>`, with `<number>` the number of a `change` ticket the ticket tracker holds.
        - The note of a line that moves a ticket into `closed` opens with its resolution, one of {resolutions}.
        - The command refuses, and neither moves nor writes, where `{log}` is not the file's last section or the note spans more than one line.
    """)

LEGACY_HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/file_issue.py <unix time> <source> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>

        ## Effect
        <its effect>

        ## Evidence
        <the evidence>
        EOF
        ```
    - The command reads one issue from stdin, names it `<unix time>-<source>-<agent>-<i>.md`, writes it under `tickets/open/` in the main tree, and prints the path it wrote.
    - `<i>` is 1 more than the largest `<i>` of a file under `tickets/` with the same time, source and agent, so the issues of one `date +%s` count from 1.
    - Give one `date +%s` as `<unix time>` to every call that files your issues.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)


class Status(StrEnum):
    """The directories under `tickets/` that a ticket's file moves between."""
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    BLOCKED = "blocked"
    CLOSED = "closed"


class Resolution(StrEnum):
    """The words the note of a line into `closed` opens with."""
    FIXED = "fixed"
    DUPLICATE = "duplicate"
    CANNOT_REPRODUCE = "cannot-reproduce"
    WONTFIX = "wontfix"
    INVALID = "invalid"


IDS = "ids"
"""The directory under `tickets/` that holds one empty file per reserved
ticket number, named by the number."""

SESSIONS = "sessions"
"""The directory under `tickets/` that holds one file per reserved session
index, named by the index, whose lines are the ids of its sessions."""

SESSION_VAR = "CLAUDE_CODE_SESSION_ID"
"""The variable of an agent's shell that holds its session's id."""


class Domain(StrEnum):
    """What a ticket's subject is."""
    TASK = "task"
    CHANGE = "change"
    COMMIT = "commit"
    TICKET = "ticket"
    AGENT = "agent"


FIELD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
"""A field of a ticket's name: kebab words, with no `_`, which separates
the fields."""

COUNT = re.compile(r"[1-9]\d*")
"""A session's index, the `<n>` of a ticket's number, or a bare number."""

TICKET_NUMBER = re.compile(rf"(?:(?P<session>{COUNT.pattern})-)?(?P<n>{COUNT.pattern})")
"""A ticket's number, `<session>-<n>`, or the bare number of a ticket filed
before a number gave the filing session's index."""

COMMIT = re.compile(r"[0-9a-f]{7,40}")

AGENT_ID = re.compile(r"a[0-9a-f]{16}")

CHANGE_SUBJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
"""A `change` ticket's own subject: its namespace, then kebab words."""


class Kind(StrEnum):
    """What a ticket is."""
    INTERFERENCE = "interference"
    DELAY = "delay"
    QUESTION = "question"
    BUG = "bug"
    PERFORMANCE = "performance"
    REFACTOR = "refactor"
    CHANGE = "change"


PASS_KINDS = frozenset({Kind.INTERFERENCE, Kind.DELAY})
EDITOR_KINDS = frozenset({Kind.QUESTION, Kind.BUG})
REVIEW_KINDS = frozenset({Kind.BUG, Kind.PERFORMANCE})

FILER_KINDS: dict[str, frozenset[Kind]] = {
    "analyze": PASS_KINDS,
    "create": PASS_KINDS,
    "refine": PASS_KINDS,
    "transcript-review": PASS_KINDS,
    "supervisor-check": PASS_KINDS,
    "handbook": PASS_KINDS,
    "handbook-expanded": PASS_KINDS,
    "code-editor": EDITOR_KINDS,
    "doc-editor": EDITOR_KINDS,
    "operator": REVIEW_KINDS,
    "doc-reviewer": REVIEW_KINDS,
    "ticket-reviewer": REVIEW_KINDS,
    "code-reviewer": REVIEW_KINDS | {Kind.REFACTOR, Kind.QUESTION},
    "main": frozenset({Kind.CHANGE}),
    "assignee": frozenset({Kind.CHANGE}),
}
"""The kinds each filing agent, by its name, may file."""


def is_agent(agent: str, name: str) -> bool:
    return agent == name or agent.startswith(f"{name}-")


def filer_kinds(agent: str) -> frozenset[Kind]:
    """The kinds `agent` may file: those of its name, or of the longest
    name it extends with `-<suffix>`. Any other name is refused."""
    for name in sorted(FILER_KINDS, key=len, reverse=True):
        if is_agent(agent, name):
            return FILER_KINDS[name]
    raise Refused(mctx("the document of `{agent}` gives it no ticket kinds: the agents that file are {names}").format(
        agent=agent, names=ticked(FILER_KINDS)))

FRONT = r"---\nkind: (?P<kind>\S+)\n(?P<fields>(?:[a-z-]+: .*\n)*)---\n"

TICKET_HEAD = re.compile(FRONT + "# ")
"""The front matter and title mark of a ticket, or of an issue filed before
tickets, in the text of a filing command."""

SECTIONS = {Kind.CHANGE: ("Intent", "Motivation", "Scope")}
"""The sections of each kind that has its own; every other kind has
`DEFECT_SECTIONS`."""

DEFECT_SECTIONS = ("Impact", "Evidence")


def sections_example(sections: tuple[str, ...]) -> str:
    """`sections` as the form in `HELP` shows them after its title, at the
    indent of that form."""
    return "".join(f"\n\n    ## {s}\n    <its {s.lower()}>" for s in sections)


def body_form(kind: Kind) -> re.Pattern[str]:
    """The title and sections that follow a `kind` ticket's front matter."""
    title = r"# .+\n" if kind is Kind.CHANGE else r"# .+: .+\n"
    sections = SECTIONS.get(kind, DEFECT_SECTIONS)
    middle = r"(?:.*\n)*".join(f"## {s}\n" for s in sections[:-1])
    return re.compile(title + r"\n" + middle + r"(?:.*\n)*" + f"## {sections[-1]}" + r"(?:\n|$)")


FIELDS = {Kind.CHANGE: frozenset({"depends-on", "priority"})}
"""The front matter fields besides `kind` that each kind may give."""

LOG = "## Log"

TIME_FORM = "%Y-%m-%dT%H:%M:%SZ"
"""The form of a log line's time, in UTC."""

HEADING = re.compile(r"^## .*$", re.MULTILINE)

RESOLUTION_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")


class Wait(StrEnum):
    """What a ticket under `blocked` waits on, the word the note of the line
    into `blocked` opens with."""
    USER = "user"
    CHANGE = "change"


WAIT = re.compile(rf"(?:{Wait.USER}|{Wait.CHANGE} (?P<change>{TICKET_NUMBER.pattern}))(?![\w-])")
"""The opening of the note of a line into `blocked`."""

LOG_LINE = re.compile(rf"^.*? (?P<status>{'|'.join(Status)}) \[(?P<agent>[^\]\s]+)"
                      rf"(?: (?P<id>{AGENT_ID.pattern}))?\](?:: (?P<note>.*))?$", re.MULTILINE)
"""A log line, of whatever time form, as the command or a hand wrote it."""

LEGACY_FORM = re.compile(r"---\nkind: (?P<kind>\S+)\n---\n# .+: .+\n\n## Effect\n(?:.*\n)*## Evidence(?:\n|$)")
"""The form `scripts/file_issue.py` takes, from agents launched before
tickets."""

LEGACY_KINDS = {"undecided": Kind.QUESTION, "gap": Kind.QUESTION}
"""The kinds an issue filed before tickets gives, mapped to the kind a ticket
gives in their place."""

NAME_PART = re.compile(r"[^\s/]+")


def ticked(names: Iterable[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)


def statuses(tickets: Path) -> list[Path]:
    return [tickets / s for s in Status]


def check_depends_on(tickets: Path, value: str) -> None:
    """Refuses a `depends-on` value that is not a list of numbers of
    tickets the ticket tracker holds."""
    for n in (part.strip() for part in value.split(",")):
        if not TICKET_NUMBER.fullmatch(n):
            raise Refused(mctx("`{n}` in `depends-on` is not a ticket number").format(n=n))
        ticket_path(tickets, n)


def checked_kind(tickets: Path, agent: str, text: str) -> Kind:
    """The kind of the ticket `text`, refused where `text` does not have
    the form `--help` shows or `agent` may not file that kind."""
    head = re.match(FRONT, text)
    if not head:
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    try:
        kind = Kind(head.group("kind"))
    except ValueError:
        raise Refused(mctx("`{kind}` is no ticket kind").format(kind=head.group("kind")))
    kinds = filer_kinds(agent)
    if kind not in kinds:
        raise Refused(mctx("`{agent}` files no `{kind}`: it files {kinds}").format(
            agent=agent, kind=kind, kinds=ticked(k for k in Kind if k in kinds)))
    keys: list[str] = []
    for line in head.group("fields").splitlines():
        key, value = line.split(": ", 1)
        if key in keys:
            raise Refused(mctx("the front matter gives `{key}` twice").format(key=key))
        keys.append(key)
        if key not in FIELDS.get(kind, frozenset()):
            raise Refused(mctx("a `{kind}` gives no `{key}`").format(kind=kind, key=key))
        if key == "priority" and not (value.isdigit() and 0 <= int(value) <= 100):
            raise Refused(mctx("`priority` `{value}` is not an integer from 0 to 100").format(value=value))
        if key == "depends-on":
            check_depends_on(tickets, value)
    if not body_form(kind).match(text, head.end()):
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    if re.search(f"^{LOG}$", text, re.MULTILINE):
        raise Refused(mctx("the ticket on stdin has a `{log}` section, which the command writes").format(log=LOG))
    return kind


def logged(text: str, status: Status, agent: str) -> str:
    """`text` with a `## Log` that gives its filing time."""
    return f"{text.rstrip(chr(10))}\n\n{LOG}\n{log_line(status, agent, None, 'filed')}"


def log_line(status: Status, agent: str, agent_id: str | None, note: str | None) -> str:
    """A log line, stamped now."""
    holder = f"{agent} {agent_id}" if agent_id else agent
    line = f"{time.strftime(TIME_FORM, time.gmtime())} {status} [{holder}]"
    return f"{line}: {note}\n" if note else f"{line}\n"


def reserve(tickets: Path, session: int) -> str:
    """Reserves the next number of a ticket of the session with index
    `session` by an exclusive create of its file under `tickets/ids/`,
    moving to the next number where another call created that file
    first."""
    ids = tickets / IDS
    ids.mkdir(parents=True, exist_ok=True)
    n = max((int(m["n"]) for p in ids.iterdir()
             if (m := TICKET_NUMBER.fullmatch(p.name)) and m["session"] == str(session)), default=0) + 1
    while True:
        number = f"{session}-{n}"
        try:
            os.close(os.open(ids / number, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return number
        except FileExistsError:
            n += 1


@contextmanager
def staged(directory: Path, text: str) -> Iterator[Path]:
    """A file under `directory` that holds `text` whole, for `link_new` to
    give its names, removed on exit."""
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        yield Path(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def link_new(source: Path, path: Path) -> bool:
    try:
        os.link(source, path)
        return True
    except FileExistsError:
        return False


def write_new(directory: Path, text: str, names: Iterable[str]) -> Path:
    """Writes `text` under `directory` at the first name `names` yields
    that no file holds, and returns its path. The file appears whole or not
    at all, and an existing file is never replaced."""
    with staged(directory, text) as tmp:
        for name in names:
            if link_new(tmp, path := directory / name):
                return path
        raise AssertionError("`names` ended")


def session_id() -> str:
    session = os.environ.get(SESSION_VAR)
    if not session:
        raise Refused(mctx("the shell holds no session id in `{var}`").format(var=SESSION_VAR))
    return session


def indexes(tickets: Path) -> dict[int, list[str]]:
    directory = tickets / SESSIONS
    if not directory.is_dir():
        return {}
    return {int(p.name): p.read_text().split() for p in directory.iterdir() if COUNT.fullmatch(p.name)}


def indexed(reserved: dict[int, list[str]], session: str) -> int | None:
    held = [i for i, ids in reserved.items() if session in ids]
    if len(held) > 1:
        raise Refused(mctx("session `{session}` has more than one index: {held}").format(
            session=session, held=ticked(str(i) for i in sorted(held))))
    return held[0] if held else None


def session_index(tickets: Path, session: str) -> int:
    """The index of the session with id `session`, reserved where it has
    none: the index of the session it was forked from, with `session`
    added to that index's file, or else the next index, by a file created
    whole that holds `session`. Where another call created the file of the
    index tried first, the call looks again for an index of `session`
    before it tries the next."""
    found = indexed(indexes(tickets), session)
    if found is not None:
        return found
    parent = forked_from(find(session))
    if parent is not None:
        index = session_index(tickets, parent)
        add_session(tickets / SESSIONS / str(index), session)
        return index
    directory = tickets / SESSIONS
    with staged(directory, f"{session}\n") as tmp:
        while True:
            reserved = indexes(tickets)
            found = indexed(reserved, session)
            if found is not None:
                return found
            n = max(reserved, default=0) + 1
            if link_new(tmp, directory / str(n)):
                return n


def add_session(path: Path, session: str) -> None:
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        if session not in path.read_text().split():
            f.write(f"{session}\n")


def check_subject(tickets: Path, domain: Domain, subject: str) -> None:
    """Refuses a `subject` that is no id of a thing of `domain`: a task
    with no file, a ticket the ticket tracker does not hold, a hash of no commit, or
    no agent id."""
    match domain:
        case Domain.TASK:
            known = task_file(subject).exists()
        case Domain.CHANGE | Domain.TICKET:
            ticket_path(tickets, subject)
            known = True
        case Domain.COMMIT:
            known = bool(COMMIT.fullmatch(subject)) and checkout.git(
                checkout.ROOT, "cat-file", "-e", f"{subject}^{{commit}}").returncode == 0
        case Domain.AGENT:
            known = bool(AGENT_ID.fullmatch(subject))
    if not known:
        raise Refused(mctx("`{subject}` is no `{domain}` id").format(subject=subject, domain=domain))


def file_ticket(tickets: Path, domain: str, subject: str, agent: str, text: str) -> Path:
    """Writes `text` as a ticket of the agent's session under its first
    status and returns its path."""
    try:
        dom = Domain(domain)
    except ValueError:
        raise Refused(mctx("`{domain}` is no domain: the domains are {domains}").format(
            domain=domain, domains=ticked(Domain)))
    if not FIELD.fullmatch(agent):
        raise Refused(mctx("`{agent}` is not kebab words").format(agent=agent))
    kind = checked_kind(tickets, agent, text)
    if kind is Kind.CHANGE:
        subject = subject.replace("_", "-")
    if not FIELD.fullmatch(subject):
        raise Refused(mctx("`{subject}` is not kebab words").format(subject=subject))
    if kind is Kind.CHANGE:
        if dom is not Domain.CHANGE or not CHANGE_SUBJECT.fullmatch(subject):
            raise Refused(mctx("a `change` takes `change` and `<namespace>-<short-title>`"))
    else:
        check_subject(tickets, dom, subject)
    status = Status.DRAFT if kind is Kind.CHANGE else Status.OPEN
    number = reserve(tickets, session_index(tickets, session_id()))
    name = f"{number}_{dom}_{subject}_{agent}.md"
    return write_new(tickets / status, logged(text, status, agent), [name])


def ticket_path(tickets: Path, ref: str) -> Path:
    """The path of the ticket numbered `ref`, or named `ref` where it was
    filed before tickets had numbers, in whichever status it stands."""
    stem = ref.removesuffix(".md")
    if not re.fullmatch(r"[\w.-]+", stem):
        raise Refused(mctx("`{ref}` is no ticket number or name").format(ref=ref))
    numbered = bool(TICKET_NUMBER.fullmatch(stem))
    pattern = f"{stem}_*.md" if numbered else f"{stem}.md"
    found = sorted(p for d in statuses(tickets) for p in d.glob(pattern))
    if len(found) == 1:
        return found[0]
    if found:
        raise Refused(mctx("ticket `{ref}` stands at more than one path: {paths}").format(
            ref=ref, paths=", ".join(str(p) for p in found)))
    if numbered and (tickets / IDS / stem).exists():
        raise Refused(mctx("ticket number `{ref}` is reserved, and no ticket has it").format(ref=ref))
    raise Refused(mctx("no ticket is `{ref}`").format(ref=ref))


def read_ticket(path: Path) -> str:
    """The text of the ticket at `path`, refused where its file moved after
    `ticket_path` found it."""
    try:
        return path.read_text()
    except FileNotFoundError:
        raise Refused(mctx("{path} moved before this call could read it").format(path=path))


def check_line(status: Status, moves: bool, agent: str, agent_id: str | None,
               note: str | None) -> None:
    """Refuses a log line the ticket notes do not give."""
    if not FIELD.fullmatch(agent):
        raise Refused(mctx("`{agent}` is not kebab words").format(agent=agent))
    if agent_id is not None and not AGENT_ID.fullmatch(agent_id):
        raise Refused(mctx("`{id}` is no agent id").format(id=agent_id))
    if agent_id is None and status is Status.ASSIGNED:
        raise Refused(mctx("an `assigned` line takes your agent id in `--id`"))
    if note is not None and (not note.strip() or "\n" in note or "\r" in note):
        raise Refused(mctx("the note is not one line of text"))
    if moves and status is Status.CLOSED:
        word = RESOLUTION_WORD.match(note or "")
        if not word or word.group() not in set(Resolution):
            raise Refused(mctx("the note of a move into `closed` opens with one of {resolutions}").format(
                resolutions=ticked(Resolution)))


def check_wait(tickets: Path, note: str | None) -> None:
    """Refuses the note of a line into `blocked` that does not open with
    what the ticket waits on, or that names as the change it waits on a
    ticket that is no `change`."""
    wait = WAIT.match(note or "")
    if wait is None:
        raise Refused(mctx("the note of a move into `{blocked}` opens with `{user}` or `{change} <number>`").format(
            blocked=Status.BLOCKED, user=Wait.USER, change=Wait.CHANGE))
    if wait["change"] is None:
        return
    path = ticket_path(tickets, wait["change"])
    head = re.match(FRONT, read_ticket(path))
    if not head or head["kind"] != Kind.CHANGE:
        raise Refused(mctx("ticket `{n}` is no `change`").format(n=wait["change"]))


def log_lines(text: str) -> list[re.Match[str]]:
    """The lines of `text`'s log that have the form of a log line."""
    log = [m for m in HEADING.finditer(text) if m.group() == LOG]
    return list(LOG_LINE.finditer(text, log[-1].end())) if log else []


def holder(text: str) -> str | None:
    """The agent id of the holder of the ticket `text`: the id of the last
    `assigned` line that gives one, in its bracket or, in a line written
    before the bracket held it, as its note's first word, among the lines
    of the log's final run of `assigned` lines. None where none of them
    gives one."""
    for line in reversed(log_lines(text)):
        if line["status"] != Status.ASSIGNED:
            break
        if line["id"]:
            return line["id"]
        first = (line["note"] or "").split(" ", 1)[0].rstrip(";,.:")
        if AGENT_ID.fullmatch(first):
            return first
    return None


def check_take(text: str, agent_id: str) -> None:
    """Refuses an `assigned` line that gives `agent_id` on a ticket already
    under `assigned`, unless `agent_id` holds it: such a line on a ticket
    another agent took is the move that fails."""
    held = holder(text)
    if held != agent_id:
        raise Refused(mctx("the ticket stands under `assigned`, held by {holder}").format(
            holder=f"`{held}`" if held else "no agent"))


def status_of(word: str) -> Status:
    try:
        return Status(word)
    except ValueError:
        raise Refused(mctx("`{status}` is no status: the statuses are {statuses}").format(
            status=word, statuses=ticked(Status)))


def write_log(tickets: Path, ref: str, status: str, agent: str, source: str, agent_id: str | None,
              note: str | None) -> Path:
    """Moves ticket `ref` from `source`'s directory to `status`'s where
    they differ, then appends a log line to it, and returns its path. The
    move is a rename, and a call refuses where the ticket no longer stands
    in `source`, so of two calls that move one file, the later one is
    refused, as `mv` from `source`'s directory would be."""
    to, origin = status_of(status), status_of(source)
    path = ticket_path(tickets, ref)
    if path.parent.name != origin:
        raise Refused(mctx("ticket `{ref}` stands in `{actual}`, not `{origin}`").format(
            ref=ref, actual=path.parent.name, origin=origin))
    moves = origin != to
    check_line(to, moves, agent, agent_id, note)
    if moves and to is Status.BLOCKED:
        check_wait(tickets, note)
    text = read_ticket(path)
    headings = HEADING.findall(text)
    if not headings or headings[-1] != LOG:
        raise Refused(mctx("`{log}` is not the last section of {path}").format(log=LOG, path=path))
    if not moves and to is Status.ASSIGNED and agent_id:
        check_take(text, agent_id)
    if moves:
        target = tickets / to / path.name
        target.parent.mkdir(exist_ok=True)
        try:
            os.rename(path, target)
        except FileNotFoundError:
            raise Refused(mctx("{path} moved before this call could move it").format(path=path))
        path = target
    with path.open("a") as f:
        # A line written by hand may lack its newline.
        if not path.read_text().endswith("\n"):
            f.write("\n")
        f.write(log_line(to, agent, agent_id, note))
    return path


def file_legacy(tickets: Path, unix_time: str, source: str, agent: str, text: str) -> Path:
    """Writes an issue in the form `scripts/file_issue.py` takes as a
    ticket under `tickets/open/`, with the kind and section an issue gives
    under the names a ticket gives them, and returns its path."""
    if not unix_time.isdigit():
        raise Refused(mctx("the unix time `{time}` is not a number").format(time=unix_time))
    for part in (source, agent):
        if not NAME_PART.fullmatch(part):
            raise Refused(mctx("`{part}` is not one word without `/`").format(part=part))
    form = LEGACY_FORM.match(text)
    if not form:
        raise Refused(mctx("the issue on stdin does not have the form `--help` shows"))
    old = form.group("kind")
    try:
        kind = LEGACY_KINDS.get(old) or Kind(old)
    except ValueError:
        raise Refused(mctx("`{kind}` is no issue kind").format(kind=old))
    text = text.replace(f"kind: {old}\n", f"kind: {kind}\n", 1).replace("\n## Effect\n", "\n## Impact\n", 1)
    prefix = f"{unix_time}-{source}-{agent}-"
    taken = [int(m.group(1)) for d in statuses(tickets)
             for p in d.glob(f"{prefix}*.md")
             if (m := re.fullmatch(re.escape(prefix) + r"(\d+)\.md", p.name))]
    start = max(taken, default=0) + 1
    names = (f"{prefix}{i}.md" for i in range(start, sys.maxsize))
    return write_new(tickets / Status.OPEN, logged(text, Status.OPEN, agent), names)


def main_tickets() -> Path:
    return checkout.main_worktree(checkout.ROOT) / "tickets"


@dataclass(frozen=True)
class Filing:
    """A filing command: its script under `scripts/`, and the script to
    file with where the main tree has no copy of it."""
    script: str
    fallback: str


TICKET_FILING = Filing("file_ticket.py", "file_issue.py")
LEGACY_FILING = Filing("file_issue.py", "file_ticket.py")


def filed_in_main(filing: Filing, args: list[str]) -> int | None:
    """Runs the main tree's copy of `filing` with `args` and this process's
    stdin, and returns its exit status, where this copy is another one;
    None where this copy is the main tree's."""
    main = checkout.main_worktree(checkout.ROOT)
    copy = main / "scripts" / filing.script
    if (checkout.scripts() / filing.script).resolve() == copy.resolve():
        return None
    if not copy.exists():
        raise Refused(mctx("the main tree has no `scripts/{script}`: file with `scripts/{fallback}`").format(
            script=filing.script, fallback=filing.fallback))
    # This copy's environment, which `uv` would name as not the main tree's.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(["uv", "run", "--project", str(main), "python", str(copy), *args],
                          env=env).returncode


def run(args: Sequence[str | None], help_text: str, count: int, act: Callable[..., Path | int],
        filing: Filing | None, argv: list[str]) -> int:
    """Runs a command that takes `count` arguments, and stdin where `act`
    reads it, printing what `act` returns. A `filing` runs in the main
    tree's copy of its script, given `argv`, the call's arguments."""
    if args and args[0] in ("--help", "-h"):
        print(help_text)
        return 0
    if len(args) != count:
        print(help_text, file=sys.stderr)
        return 2
    try:
        status = filed_in_main(filing, argv) if filing else None
        if status is not None:
            return status
        print(act(*args))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 1
    return 0


def log_args(args: list[str]) -> list[str | None]:
    """The arguments of `log` as `write_log` takes them after `tickets`,
    with None for an agent id or a note the call does not give. Arguments
    in another form come back as given, which `run` refuses by their
    count."""
    head, rest = args[:3], args[3:]
    options: dict[str, str] = {}
    while rest[:1] in (["--from"], ["--id"]) and len(rest) >= 2 and rest[0] not in options:
        options[rest[0]] = rest[1]
        rest = rest[2:]
    if len(head) < 3 or "--from" not in options or len(rest) > 1 or rest[:1] in (["--from"], ["--id"]):
        return list(args)
    return [*head, options["--from"], options.get("--id"), rest[0] if rest else None]


def main(args: list[str]) -> int:
    help_text = HELP.format(domains=ticked(Domain),
                            defect_sections=sections_example(DEFECT_SECTIONS),
                            change_sections=sections_example(SECTIONS[Kind.CHANGE]),
                            statuses=ticked(Status), log=LOG, time_form=TIME_FORM,
                            resolutions=ticked(Resolution), blocked=Status.BLOCKED,
                            user=Wait.USER, change=Wait.CHANGE, session_var=SESSION_VAR,
                            sessions=SESSIONS)
    if args[:1] == ["path"]:
        return run(args[1:], help_text, 1, lambda ref: ticket_path(main_tickets(), ref), None, args)
    if args[:1] == ["index"]:
        return run(args[1:], help_text, 0, lambda: session_index(main_tickets(), session_id()),
                   TICKET_FILING, args)
    if args[:1] == ["log"]:
        return run(log_args(args[1:]), help_text, 6, lambda *a: write_log(main_tickets(), *a),
                   TICKET_FILING, args)
    return run(args, help_text, 3, lambda domain, subject, agent: file_ticket(
        main_tickets(), domain, subject, agent, sys.stdin.read()), TICKET_FILING, args)


def legacy_main(args: list[str]) -> int:
    return run(args, LEGACY_HELP, 3, lambda unix_time, source, agent: file_legacy(
        main_tickets(), unix_time, source, agent, sys.stdin.read()), LEGACY_FILING, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
