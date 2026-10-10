"""File a ticket under the main tree's `tickets/`, from the main tree or any
worktree of it, print a ticket's path, make a ticket's transitions and
write its log lines, and list the open tickets a ticket analyst settles.
`HELP`, which `--help` prints, says how an agent files, and each
subcommand's own help, which its `--help` prints, how an agent calls it."""

import re
import subprocess
import sys
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from arc.task import task_file
from controlled_markdown import mctx
from operations.roles import EDITORS
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from ticket_files import FIELD, NAME_FORM, TicketName, ticket_path  # noqa: E402
from ticket_form import (DEFAULT_PRIORITY, DEFECT_SECTIONS, DESIGN, LOG, MECHANICAL, SECTIONS,  # noqa: E402
                         checked_kind, heading, sections_example)
from ticket_log import (AGENT_ID, CLOSED_BY, UNBLOCKED_BY, VALIDATING, Wait,  # noqa: E402
                        log_moves, logged, status_of)
from ticket_numbers import (SESSION_VAR, SESSIONS, reserve, session_id,  # noqa: E402
                            session_index, ticket_number, write_new)
from ticket_settle import to_settle  # noqa: E402
from ticketing.times import TIME_FORM  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402
from ticketing.vocabulary import MANY_IDEAS, Domain, Kind, Resolution, Status  # noqa: E402
from transcripts import Refused  # noqa: E402

HELP = mctx("""
    - `{invocation} <domain> <subject> <agent>` files the ticket on its stdin under the main tree's `tickets/`, and prints the path it wrote.
    {subcommands}
    - Usage:
        ```
        {invocation} <domain> <subject> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>{defect_sections}
        EOF
        ```
    - A `change` takes `kind: change` and `editors: <editor>, <editor>`, with each editor the change needs among {editors}, may add `depends-on: <number>, <number>`, `priority: <0 to 100>` (`{default_priority}` where it gives none), `after-merge: <the checks its Scope places after the merge>` and `mechanical: {mechanical}` to the front matter, gives `mechanical` only where its Intent gives each edit under `src/` and `scripts/` outright, so that its code editors make no design choice, has `# <title>` as its title, and has the sections {change_sections} in place of {defect_headings}, with, where it adds a mechanism to code, a `{design}` section after `## Intent`, which gives the existing operations the change uses or extends and each new operation with its module.
    - A `request` has `# <target>: <what the user asks for>` as its title, and the sections {request_sections} in place of {defect_headings}.
    - The rules of `<domain>`, `<subject>`, `<agent>`, numbers and filing follow.
    - `<domain>` is one of {domains}, and `<subject>` is the id of the thing it names: a task id for `task`, a ticket's number for `change` and `ticket`, a commit hash for `commit`, an agent id for `agent`. A ticket that asks for a change, a `change` or a `request`, takes `change` as `<domain>` and `<namespace>-<short-title>` as `<subject>`, and each `_` in that `<subject>`, as in a namespace name such as `run_dl`, becomes `-`.
    - `<agent>` is your agent's name, which may end in `-<suffix>`. The command refuses a kind your agent may not file, and names the kinds it may.
    - A ticket's number is `<session>-<n>`: `<session>` is the index of the session that filed it, and `<n>` counts that session's tickets from 1. A ticket filed before a number gave the filing session's index has a bare number, and the command takes either form wherever it takes a number.
    - Numbers order with every bare number before every `<session>-<n>` number. Bare numbers compare as integers, and `<session>-<n>` numbers compare by `<session>`, then by `<n>`, each as an integer.
    - The session that files is the one whose id the filing agent's shell holds in `{session_var}`, in a subagent as in the main session. The command refuses a filing where the shell holds none.
    - A session's index has a file under `tickets/{sessions}/`, named by the index, that holds the session's id. A session forked from another takes the index of the session it was forked from, and the file then holds both ids, one per line.
    - The command reserves the ticket's number, names the ticket `{name_form}`, writes it under `tickets/draft/` for a `change` and `tickets/open/` for any other kind in the main tree, with the filing time in the first line of its `## Log`, and prints the path it wrote.
    - Run from a worktree, the command files with the main tree's copy of `scripts/file_ticket.py`, and refuses where the main tree has none.
    - Each `<number>` in `depends-on` is the number of a ticket the ticket tracker holds.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)
"""The help of filing, which `--help` with no subcommand prints."""

SUBCOMMAND_LINE = mctx("""
    - `{name}` {purpose}: `{invocation} {name} --help` prints its form.
    """)

SUBCOMMAND_HELP = mctx("""
    - `{invocation} {name}{args}` {purpose}.
    {detail}
    """)

PATH_HELP = mctx("""
    - The ticket is the one with that number, in whichever status it stands.
    """)

LOG_HELP = mctx("""
    - The ticket is the one with that number, and the command prints its path.
    - `<status>` and `<current status>` are each one of {statuses}. `<current status>` is the status you saw the ticket in.
    - The command refuses, and neither moves nor writes, where the ticket stands in another status than `<current status>`, or where its file moves before the command moves it.
    - Where `<status>` differs from `<current status>`, the command moves the ticket's file to the directory of `<status>`. Where they are the same, the log line moves nothing.
    - The command appends `<time> <status> [<agent>]: <note>` to the file's `{log}`, with the time in UTC in the form `{time_form}`, and with `<agent> <agent id>` in the bracket where `--id` gives an agent id. A line with no `<note>` ends at the bracket.
    - An `assigned` line that moves a ticket into `assigned` takes, in `--id`, the agent id of the agent that writes it.
    - On a ticket that already stands in `assigned`, the command refuses an `assigned` line whose `--id` does not hold the ticket, and accepts one with no `--id`. The holder is the agent id of the last `assigned` line that gives one, in its bracket or as the first word of its note, among the log's final run of `assigned` lines. Where none of them gives one, the ticket has no holder.
    - The note of a line that moves a ticket into `{blocked}` opens with what the ticket waits on: `{user}`, `{validation}`, or `{change} <number>`, with `<number>` the number of a `change` ticket the ticket tracker holds. `{validation}` is the wait of a `{request}` whose need a change met, until the coordinator reads a run that exercises that change.
    - The note of a line that moves a ticket into `closed` opens with its resolution, one of {resolutions}.
    - Where a line would move a `{request}` into `closed` with `{fixed}`, other than from `{blocked}` where the request waits on `{validation}`, the command leaves the request under `{blocked}`, or moves it there, with the note `{validating}`, and prints the path it went to. This holds whichever agent writes the line, and for the lines below that close tickets that wait on a change.
    - Where the line moves a `{change}` ticket into `closed`, the command also moves each ticket under `{blocked}` that waits on that change, and prints the path of each one it moved, one per line, after the change's own path.
    - A ticket waits on the change that the last line of its log whose note opens with what a ticket waits on gives as `{change} <number>`.
    - Where the change's resolution is `{fixed}`, each ticket that waits on it moves into `closed`, with the note `{closed_by}`. Where the resolution is another, each moves into `open`, with the note `{unblocked_by}`. Each such line takes the `<agent>` and the `--id` of the call.
    - A ticket that waits on the change and that another call moves first, the command skips. A `{change}` ticket that the command moves into `closed` this way moves the tickets that wait on it in turn.
    - The command moves those tickets in the order of their file names. Where the move of one is refused for another reason, the command moves the others, prints the path of each ticket it moved, and then refuses, with the change's path and the path of each ticket it did not move, with the reason. That holds as well for the tickets that wait on a `{change}` the command closes this way.
    - The command refuses, and neither moves nor writes, where `{log}` is not the file's last section or the note spans more than one line.
    """)

TO_SETTLE_HELP = mctx("""
    - The list holds each ticket under `tickets/open/` that your session filed or whose number the call gives.
    - The list leaves out:
        - each `{change_kind}`, which an operator runs;
        - each `{question}` filed on a change whose ticket stands outside `tickets/closed/`, which the ticket analyst of that change decides before its merge;
        - each `{refactor}` whose title ends in `{many_ideas}`, which the editor that next edits its module carries out first.
    - A `{question}` with the `<domain>` `{change_domain}` is filed on the change its `<subject>` gives.
    - The command prints the number of each ticket the list holds, one per line, in the order of numbers, or `{empty}` where it holds none.
    - The command refuses where a number the call gives names no ticket, where the front matter of a ticket the list would hold gives no kind, where a `{refactor}` it would hold has no title, or where a `{question}` filed on a change names no ticket the ticket tracker holds.
    """)

EMPTY = mctx("the list is empty")


COMMIT = re.compile(r"[0-9a-f]{7,40}")

CHANGE_SUBJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
"""The subject of a ticket that asks for a change: its namespace, then
kebab words."""

ASKS_CHANGE = frozenset({Kind.CHANGE, Kind.REQUEST})


def check_subject(tickets: Path, domain: Domain, subject: str) -> None:
    """Refuses a `subject` that is no id of a thing of `domain`: a task
    with no file, a ticket the ticket tracker does not hold, a hash of no commit, or
    no agent id."""
    match domain:
        case Domain.TASK:
            known = task_file(subject).exists()
        case Domain.CHANGE | Domain.TICKET:
            ticket_path(tickets, ticket_number(subject))
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
    if kind in ASKS_CHANGE:
        subject = subject.replace("_", "-")
    if not FIELD.fullmatch(subject):
        raise Refused(mctx("`{subject}` is not kebab words").format(subject=subject))
    if kind in ASKS_CHANGE:
        if dom is not Domain.CHANGE or not CHANGE_SUBJECT.fullmatch(subject):
            raise Refused(mctx("a `{kind}` takes `change` and `<namespace>-<short-title>`").format(kind=kind))
    else:
        check_subject(tickets, dom, subject)
    status = Status.DRAFT if kind is Kind.CHANGE else Status.OPEN
    number = reserve(tickets, session_index(tickets, session_id()))
    name = TicketName(number, dom, subject, agent).file_name
    return write_new(tickets / status, logged(text, status, agent), [name])


def main_tickets() -> Path:
    return checkout.main_worktree(checkout.ROOT) / "tickets"


SCRIPT = "file_ticket.py"

INVOCATION = f"uv run python scripts/{SCRIPT}"
"""The command that runs this script, as a help text writes it."""


def filed_in_main(args: list[str]) -> int | None:
    """Runs the main tree's copy of this script with `args` and this
    process's stdin, and returns its exit status, where this copy is
    another one; None where this copy is the main tree's."""
    main = checkout.main_worktree(checkout.ROOT)
    copy = main / "scripts" / SCRIPT
    if (checkout.scripts() / SCRIPT).resolve() == copy.resolve():
        return None
    if not copy.exists():
        raise Refused(mctx("the main tree has no `scripts/{script}`").format(script=SCRIPT))
    return subprocess.run(["uv", "run", "--project", str(main), "python", str(copy), *args],
                          env=checkout.tree_env()).returncode


def run(args: Sequence[str | None], help_text: str, count: int | None,
        act: Callable[..., Path | int | str], in_main: bool, argv: list[str]) -> int:
    """`argv` is the call's arguments as given, which the main tree's copy
    takes in place of `args` where `in_main` holds."""
    if args and args[0] in ("--help", "-h"):
        print(help_text)
        return 0
    if count is not None and len(args) != count:
        print(help_text, file=sys.stderr)
        return 2
    try:
        status = filed_in_main(argv) if in_main else None
        if status is not None:
            return status
        print(act(*args))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 1
    return 0


def log_args(args: list[str]) -> list[str | None]:
    """The arguments of `log` as `log_command` takes them, as text,
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


def settle_command(*given: str) -> str:
    tickets = main_tickets()
    numbers = to_settle(tickets, session_index(tickets, session_id()), map(ticket_number, given))
    return "\n".join(map(str, numbers)) if numbers else EMPTY


def log_command(ref: str, status: str, agent: str, source: str, agent_id: str | None,
                note: str | None) -> str:
    """Runs `log_moves` and returns the paths it moved tickets to, one per
    line. Where it gives a refused ticket, prints those paths, then refuses
    with the change's path and each refused ticket's path and reason."""
    moves = log_moves(main_tickets(), ticket_number(ref), status_of(status), agent, status_of(source),
                      agent_id, note)
    paths = "\n".join(map(str, moves.moved))
    if not moves.refused:
        return paths
    print(paths)
    refused = "; ".join(f"{p}: {reason}" for p, reason in moves.refused)
    raise Refused(mctx("{path} moved into `{closed}`, and these tickets that wait on it did not move: "
                       "{refused}").format(path=moves.moved[0], closed=Status.CLOSED, refused=refused))


@dataclass(frozen=True)
class Subcommand:
    """A subcommand: what it does, which its line in `HELP` and its own help
    both say, the arguments and the detail its own help adds, and how `run`
    runs it."""
    purpose: str
    args: str
    detail: str
    count: int | None
    act: Callable[..., Path | int | str]
    in_main: bool
    parse: Callable[[list[str]], Sequence[str | None]] = list


SUBCOMMANDS = {
    "log": Subcommand(mctx("makes a transition of a ticket and writes its log line"),
                      " <number> <status> <agent> --from <current status> [--id <agent id>] [<note>]",
                      LOG_HELP, 6, log_command, True, log_args),
    "path": Subcommand(mctx("prints the path of a ticket"), " <number>", PATH_HELP, 1,
                       lambda ref: ticket_path(main_tickets(), ticket_number(ref)), False),
    "index": Subcommand(mctx("prints the index of your session"), "", "", 0,
                        lambda: session_index(main_tickets(), session_id()), True),
    "to-settle": Subcommand(mctx("prints the open tickets an operator gives a ticket analyst to settle "
                                 "after a batch"),
                            " [<number> ...]", TO_SETTLE_HELP, None, settle_command, False),
}
"""Each subcommand, by the word that calls it, in the order `HELP` gives
their lines."""


def help_values() -> dict[str, str]:
    """The values each help text of `file_ticket.py` is formatted with."""
    return dict(domains=ticked(Domain), editors=ticked(map(str, EDITORS)),
                mechanical=MECHANICAL, default_priority=str(DEFAULT_PRIORITY),
                defect_sections=sections_example(DEFECT_SECTIONS),
                defect_headings=ticked(map(heading, DEFECT_SECTIONS)),
                change_sections=ticked(map(heading, SECTIONS[Kind.CHANGE])), design=heading(DESIGN),
                request_sections=ticked(map(heading, SECTIONS[Kind.REQUEST])),
                statuses=ticked(Status), log=LOG, time_form=TIME_FORM,
                resolutions=ticked(Resolution), fixed=Resolution.FIXED, blocked=Status.BLOCKED,
                user=Wait.USER, change=Wait.CHANGE, validation=Wait.VALIDATION,
                request=Kind.REQUEST,
                validating=VALIDATING.format(validation=Wait.VALIDATION, note="<note>"),
                session_var=SESSION_VAR,
                closed_by=CLOSED_BY.format(fixed=Resolution.FIXED, change=Wait.CHANGE,
                                           number="<number>", note="<note>"),
                unblocked_by=UNBLOCKED_BY.format(change=Wait.CHANGE, number="<number>",
                                                 resolution="<resolution>"),
                sessions=SESSIONS, invocation=INVOCATION, name_form=NAME_FORM,
                question=Kind.QUESTION, refactor=Kind.REFACTOR, change_kind=Kind.CHANGE,
                change_domain=Domain.CHANGE,
                many_ideas=MANY_IDEAS, empty=EMPTY,
                subcommands="\n".join(SUBCOMMAND_LINE.format(
                    invocation=INVOCATION, name=name, purpose=sub.purpose)
                    for name, sub in SUBCOMMANDS.items()))


def subcommand_help(name: str, sub: Subcommand, values: dict[str, str]) -> str:
    """The help of `sub`, which `<name> --help` prints."""
    detail = textwrap.indent(sub.detail.format(**values), "    ")
    return SUBCOMMAND_HELP.format(invocation=values["invocation"], name=name, args=sub.args,
                                  purpose=sub.purpose, detail=detail).rstrip("\n")


def main(args: list[str]) -> int:
    values = help_values()
    if args[:1] and (sub := SUBCOMMANDS.get(args[0])):
        return run(sub.parse(args[1:]), subcommand_help(args[0], sub, values), sub.count,
                   sub.act, sub.in_main, args)
    return run(args, HELP.format(**values), 3, lambda domain, subject, agent: file_ticket(
        main_tickets(), domain, subject, agent, sys.stdin.read()), True, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
