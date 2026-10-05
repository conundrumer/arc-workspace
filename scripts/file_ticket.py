"""File a ticket under the main tree's `tickets/`, from the main tree or any
worktree of it, and print a ticket's path. `HELP`, which `--help` prints,
says how an agent calls it."""

import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from arc.task import task_file
from controlled_markdown import mctx
from engine import checkout

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
        depends-on: <n>, <n>
        priority: <0 to 100>
        ---
        # <title>{change_sections}
        EOF
        ```
    - `<domain>` is one of {domains}, and `<subject>` is the id of the thing it names: a task id for `task`, a ticket number for `change` and `ticket`, a commit hash for `commit`, an agent id for `agent`. A `change` takes `change` as `<domain>` and `<namespace>-<short-title>` as `<subject>`, and each `_` in that `<subject>`, as in a namespace name such as `run_dl`, becomes `-`.
    - `<agent>` is your agent's name, which may end in `-<suffix>`. The command refuses a kind your agent may not file, and names the kinds it may.
    - The command reserves the ticket's number `<n>`, names the ticket `<n>_<domain>_<subject>_<agent>.md`, writes it under `tickets/draft/` for a `change` and `tickets/open/` for any other kind in the main tree, with the filing time in the first line of its `## Log`, and prints the path it wrote.
    - Run from a worktree, the command files with the main tree's copy of `scripts/file_ticket.py`, and refuses where the main tree has none.
    - Each `<n>` in `depends-on` is the number of a ticket the track holds.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    - `uv run python scripts/file_ticket.py path <n>` prints the path of ticket `<n>`, in whichever status it stands. It takes the name of a ticket filed before tickets had numbers in place of `<n>` too.
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
    CLOSED = "closed"


IDS = "ids"
"""The directory under `tickets/` that holds one empty file per reserved
ticket number, named by the bare number."""


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

TICKET_NUMBER = re.compile(r"[1-9]\d*")

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


def filer_kinds(agent: str) -> frozenset[Kind]:
    """The kinds `agent` may file: those of its name, or of the longest
    name it extends with `-<suffix>`. Any other name is refused."""
    for name in sorted(FILER_KINDS, key=len, reverse=True):
        if agent == name or agent.startswith(f"{name}-"):
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

LEGACY_FORM = re.compile(r"---\nkind: (?P<kind>\S+)\n---\n# .+: .+\n\n## Effect\n(?:.*\n)*## Evidence(?:\n|$)")
"""The form `scripts/file_issue.py` takes, from agents launched before
tickets."""

LEGACY_KINDS = {"undecided": Kind.QUESTION, "gap": Kind.QUESTION}
"""The kinds an issue filed before tickets gives that the track renamed."""

NAME_PART = re.compile(r"[^\s/]+")


class Refused(Exception):
    """A call the command does not carry out, with the reason."""


def ticked(names: Iterable[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)


def statuses(tickets: Path) -> list[Path]:
    return [tickets / s for s in Status]


def check_depends_on(tickets: Path, value: str) -> None:
    """Refuses a `depends-on` value that is not a list of numbers of
    tickets the track holds."""
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
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"{text.rstrip(chr(10))}\n\n{LOG}\n{stamp} {status} [{agent}]: filed\n"


def reserve(tickets: Path) -> int:
    """Reserves the next ticket number by an exclusive create of its file
    under `tickets/ids/`, moving to the next number where another call
    created that file first."""
    ids = tickets / IDS
    ids.mkdir(parents=True, exist_ok=True)
    n = max((int(p.name) for p in ids.iterdir() if TICKET_NUMBER.fullmatch(p.name)), default=0) + 1
    while True:
        try:
            os.close(os.open(ids / str(n), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return n
        except FileExistsError:
            n += 1


def write_new(directory: Path, text: str, names: Iterable[str]) -> Path:
    """Writes `text` under `directory` at the first name `names` yields
    that no file holds, and returns its path. The file appears whole or not
    at all, and an existing file is never replaced."""
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        for name in names:
            path = directory / name
            try:
                os.link(tmp, path)
                return path
            except FileExistsError:
                continue
        raise AssertionError("`names` ended")
    finally:
        Path(tmp).unlink(missing_ok=True)


def check_subject(tickets: Path, domain: Domain, subject: str) -> None:
    """Refuses a `subject` that is no id of a thing of `domain`: a task
    with no file, a ticket the track does not hold, a hash of no commit, or
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
    """Writes `text` as ticket `<n>` under its first status and returns its
    path."""
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
    n = reserve(tickets)
    name = f"{n}_{dom}_{subject}_{agent}.md"
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


def file_legacy(tickets: Path, unix_time: str, source: str, agent: str, text: str) -> Path:
    """Writes an issue in the form `scripts/file_issue.py` takes as a
    ticket under `tickets/open/`, with the kind and section the track
    renamed given their new names, and returns its path."""
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


def run(args: list[str], help_text: str, count: int, act: Callable[..., Path],
        filing: Filing | None) -> int:
    """Runs a command that takes `count` arguments, and stdin where `act`
    reads it, printing the path `act` returns. A `filing` runs in the main
    tree's copy of its script."""
    if args and args[0] in ("--help", "-h"):
        print(help_text)
        return 0
    if len(args) != count:
        print(help_text, file=sys.stderr)
        return 2
    try:
        status = filed_in_main(filing, args) if filing else None
        if status is not None:
            return status
        print(act(*args))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 1
    return 0


def main(args: list[str]) -> int:
    help_text = HELP.format(domains=ticked(Domain),
                            defect_sections=sections_example(DEFECT_SECTIONS),
                            change_sections=sections_example(SECTIONS[Kind.CHANGE]))
    if args[:1] == ["path"]:
        return run(args[1:], help_text, 1, lambda ref: ticket_path(main_tickets(), ref), None)
    return run(args, help_text, 3, lambda domain, subject, agent: file_ticket(
        main_tickets(), domain, subject, agent, sys.stdin.read()), TICKET_FILING)


def legacy_main(args: list[str]) -> int:
    return run(args, LEGACY_HELP, 3, lambda unix_time, source, agent: file_legacy(
        main_tickets(), unix_time, source, agent, sys.stdin.read()), LEGACY_FILING)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
