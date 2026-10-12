"""File a ticket under the main tree's `tickets/`, from the main tree or any
worktree of it, print a ticket's path, make a ticket's transitions and
write its log lines, list the open tickets a ticket analyst settles, and
print a ticket or the sections of it a reader names. `HELP`, which
`--help` prints, says how an agent files, and each subcommand's own help,
which its `--help` prints, how an agent calls it. `--help-all` prints a
help with the rules a well-formed call does not need, from `RULES` and
each subcommand's `rules`."""

import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from arc.task import task_file
from controlled_markdown import mctx
from operations.change_budget import EDITORS_NOTE
from operations.roles import EDITORS, Role
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from ticket_files import FIELD, NAME_FORM, TicketName, ticket_path, ticket_status  # noqa: E402
from ticket_form import (DEFAULT_PRIORITY, DESIGN, LOG, LOG_SECTION, MECHANICAL,  # noqa: E402
                         RETIRED, checked_kind, section, sections_example, ticket_kind, title_line)
from ticket_log import (AGENT_ID, CLOSED_BY, SESSION_ID, UNBLOCKED_BY, Wait,  # noqa: E402
                        log_moves, logged, read_ticket, status_of)
from ticket_numbers import (SESSION_VAR, SESSIONS, reserve, session_id,  # noqa: E402
                            session_index, ticket_number, write_new)
from ticket_settle import to_settle  # noqa: E402
from idle_sessions import MAIN, name_main, read_sessions  # noqa: E402
from ticket_reads import editors_field  # noqa: E402
from ticket_watch import (CAP, CHANGES, Case, add_evidence, budget, case_loss, evict,  # noqa: E402
                          fix_field, front, route, threshold)  # noqa: E402
from ticketing.text import SECTIONS, VALIDATION, heading  # noqa: E402
from ticketing.times import TIME_FORM  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402
from ticketing.vocabulary import (DEFECT_SECTIONS, MANY_IDEAS, Domain, Kind,  # noqa: E402
                                  Resolution, Status)
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
    - A `change` takes `kind: change` and `editors: <editor>, <editor>`, with each editor the change needs among {editors}.
        - It may add `depends-on: <number>, <number>`, `priority: <0 to 100>` (`{default_priority}` where it gives none), `after-merge: <the checks its Scope places after the merge>` and `mechanical: {mechanical}` to the front matter.
        - It gives `mechanical` only where its Intent gives each edit under `src/` and `scripts/` outright.
        - It has `# <title>` as its title, and the sections {change_sections} in place of {defect_headings}.
        - Where it adds a mechanism to code, it has a `{design}` section after `## Intent` that gives the existing operations the change uses or extends and each new operation with its module.
        - Where it adds or changes a rule or a fact in the agent-facing documents, it has that section.
    - A `request` has `# <target>: <what the user asks for>` as its title, and the sections {request_sections} in place of {defect_headings}.
        - A `request` that a `change` serves also has, before `## Log`, a `{validation}` section: what a later run must show for its need to count as met, as a command whose output shows it where one exists, and otherwise as a statement that an agent judges against a run.
    - `<domain>` is one of {domains}, and `<subject>` is the id of the thing it names: a task id for `task`, a ticket's number for `change` and `ticket`, a commit hash for `commit`, an agent id for `agent`.
        - A `change` or a `request` takes `change` as `<domain>` and `<namespace>-<short-title>` as `<subject>`, with `-` in place of each `_`.
    - `<agent>` is your agent's name.
    - A `{delay}` may give one case, `--case <agent id> <start> <end>` after `<agent>`, and then gives `fix: <editor>` in its front matter: `{invocation} case --help` gives the case's form, and `{invocation} case {full_flag}` how the command prices it and where the ticket files.
    {further}
    """)
"""The help of filing, which `--help` with no subcommand prints."""

RULES = mctx("""
    - A ticket's number is `<session>-<n>`: `<session>` is the index of the session that filed it, and `<n>` counts that session's tickets from 1.
        - A ticket filed before a number gave the filing session's index has a bare number, and the command takes either form wherever it takes a number.
    - Numbers order with every bare number before every `<session>-<n>` number.
        - Bare numbers compare as integers, and `<session>-<n>` numbers compare by `<session>`, then by `<n>`, each as an integer.
    - The session that files is the one whose id the filing agent's shell holds in `{session_var}`, in a subagent as in the main session.
        - The command refuses a filing where the shell holds none.
    - A session's index has a file under `tickets/{sessions}/`, named by the index, that holds the session's id.
        - A session forked from another takes the index of the session it was forked from, and the file then holds both ids, one per line.
    - The command reserves the ticket's number and names the ticket `{name_form}`.
        - It writes the ticket in the main tree, under `tickets/draft/` for a `change`, where `case {full_flag}` gives for a `{delay}` that gives a case, and under `tickets/open/` for any other, with the filing time in the first line of its `## Log`.
    - Run from a worktree, the command files with the main tree's copy of `scripts/file_ticket.py`, and refuses where the main tree has none.
    - Each `<number>` in `depends-on` is the number of a ticket the ticket tracker holds.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)
"""The rules of numbers, sessions and filing, which `--help-all` with no
subcommand prints after `HELP`."""

SUBCOMMAND_LINE = mctx("""
    - `{name}` {purpose}: `{invocation} {name} --help` prints its form.
    """)

SUBCOMMAND_HELP = mctx("""
    - `{invocation} {name}{args}` {purpose}.
    {detail}
    {further}
    """)

FULL_FLAG = "--help-all"

FURTHER = mctx("""
    - `{call} {full_flag}` prints this help with the rest of its rules.
    """)

PATH_HELP = mctx("""
    - The ticket is the one with that number, in whichever status it stands.
    """)

LOG_HELP = mctx("""
    - `<status>` and `<current status>` are each one of {statuses}.
        - `<current status>` is the status you saw the ticket in.
    - A line that moves a ticket into `assigned` takes, in `--id`, the agent id of the agent that writes it, or the session id of a session that writes it for itself.
    - The note of a line that moves a ticket into `{blocked}` opens with what the ticket waits on: `{user}` or `{change} <number>`, with `<number>` the number of a `change` ticket the ticket tracker holds.
    - A ticket waits on the change that the last line of its log whose note opens with what a ticket waits on gives as `{change} <number>`.
    - The note of a line that moves a ticket into `closed` opens with its resolution, one of {resolutions}.
    """)

LOG_RULES = mctx("""
    - The ticket is the one with that number, and the command prints its path.
    - The command refuses, and neither moves nor writes, where the ticket stands in another status than `<current status>`, or where its file moves before the command moves it.
    - Where `<status>` differs from `<current status>`, the command moves the ticket's file to the directory of `<status>`.
    - The command appends `<time> <status> [<agent>]: <note>` to the file's `{log}`, with the time in UTC in the form `{time_form}`, and with `<agent> <id>` in the bracket where `--id` gives an id.
        - `--id` takes an agent id, or the session id `$CLAUDE_CODE_SESSION_ID` holds.
        - A line with no `<note>` ends at the bracket.
    - On a ticket that already stands in `assigned`, the command refuses an `assigned` line whose `--id` does not hold the ticket, and accepts one with no `--id`.
        - The holder is the agent id or the session id of the last `assigned` line that gives one, in its bracket or as the first word of its note, among the log's final run of `assigned` lines.
            - Where none of them gives one, the ticket has no holder.
    - Where the line moves a `{change}` ticket into `closed`, the command also moves each ticket under `{blocked}` that waits on that change, and prints the path of each one it moved, one per line, after the change's own path.
    - A `{change}` ticket that waits on it moves into `open`, with the note `{unblocked_by}`, whatever the change's resolution.
    - Each other ticket that waits on it moves into `closed`, with the note `{closed_by}`, where the change's resolution is `{fixed}`, and into `open`, with the note `{unblocked_by}`, where it is another.
    - Each line that moves a ticket that waits on the change takes the `<agent>` and the `--id` of the call.
    - A ticket that waits on the change and that another call moves first, the command skips.
    - The command moves those tickets in the order of their file names.
        - Where the move of one is refused for another reason, the command moves the others, prints the path of each ticket it moved, and then refuses, with the change's path and the path of each ticket it did not move, with the reason.
    - The command refuses, and neither moves nor writes, where `{log}` is not the file's last section or the note spans more than one line.
    """)

TO_SETTLE_HELP = mctx("""
    - The list holds each ticket under `tickets/open/` that your session filed or whose number the call gives.
        - Where your session is the main session, as `{invocation} main --help` defines it, the list also holds each ticket under `tickets/open/` that a session in which no agent runs filed.
    - The command prints the number of each ticket the list holds, one per line, in the order of numbers, or `{empty}` where it holds none.
    """)

TO_SETTLE_RULES = mctx("""
    - The list leaves out each `{change_kind}`, each `{question}` filed on a change whose ticket stands outside `tickets/closed/`, and each `{refactor}` whose title ends in `{many_ideas}`.
    - A `{question}` with the `<domain>` `{change_domain}` is filed on the change its `<subject>` gives.
    - The command refuses where a number the call gives names no ticket, where the front matter of a ticket the list would hold gives no kind, where a `{refactor}` it would hold has no title, or where a `{question}` filed on a change names no ticket the ticket tracker holds.
    """)

MAIN_HELP = mctx("""
    - The main session is the one whose operators act on the tickets of each other session in which no agent runs as on its own.
    - `<session id>` is the id of the session the user picks.
    """)

MAIN_RULES = mctx("""
    - The command writes `<session id>` to `tickets/main`, in place of what it holds, and removes `tickets/main-wanted`, the mark that a session has asked the user to pick a main session.
    """)

CASE_HELP = mctx("""
    - In both forms below, `<agent id>` is the run the case was lost in, and `<start>` and `<end>` are the span of its extra calls, each in the form `{time_form}`.
    - Filing a `{delay}` with a case: `{invocation} <domain> <subject> <agent> --case <agent id> <start> <end>`.
        - The text on stdin gives `fix: <editor>` in its front matter, with the editor its fix would need among {editors}.
    - Appending a case: the usage line above.
        - `<number>` is the number of a ticket that stands under `tickets/{watching}/`.
    """)

CASE_RULES = mctx("""
    - The command prices a case: its dollars are the token cost of the run's requests in the span, plus the growth of the run's context across the span at the cache-read price of the run's model once for each later request of the run, and its seconds are the span's wall time.
        - It records them in a log line of the ticket.
    - The threshold of an editor is the median cost of the most recent {changes} `{change_kind}` tickets closed `{fixed}` with a known cost whose `editors` give that editor.
        - A change's cost is the token cost of the runs the line that closes it gives and of the runs under them.
    - Filing a `{delay}` with a case:
        - The ticket files under `tickets/{watching}/` where the case's dollars are below the threshold of its `fix`, and under `tickets/{open}/` otherwise.
            - Where the case's cost or the threshold is unknown, it files under `tickets/{open}/`, with an `undecided` line on stderr.
        - `tickets/{watching}/` holds at most {cap} tickets.
            - A filing that would put one more there first closes `{wontfix}` the watching ticket with the lowest loss rate, its summed dollars over the days since its first case, with its summed dollars and seconds in the note.
    - Appending a case:
        - The command adds the text on stdin to the end of the ticket's `## Evidence`, and appends the case's log line, whatever the case's own loss.
        - Where the summed dollars of the ticket's cases reach the threshold of its `fix` or pass it, the command moves the ticket to `tickets/{open}/` with a log line that gives the sum and the threshold, and prints the path it went to.
        - Where a request of the run has no price, or the threshold of the ticket's `fix` is unknown, the command moves the ticket to `tickets/{open}/`, and prints an `undecided` line on stderr.
    """)

SHOW_HELP = mctx("""
    - The command prints the ticket's path and its title line, and then each named section, from its heading to the next heading, in the order the call names them.
        - Where the call names no section, it prints the path and then the whole ticket.
    - A `<section>` is the text of a heading after its mark, as `{log_section}` for `{log}`.
    """)

EDITORS_HELP = mctx("""
    - `<number>` is the number of a `{change_kind}` ticket that stands under `tickets/{assigned}/`, `<editor>` one of {editors} that its `editors` field does not give, and `<agent id>` the holder of the ticket.
    - The command adds `<editor>` to the ticket's `editors` field, appends a log line with the budget of the change for its new `editors` set, and prints the ticket's path.
    """)

EDITORS_RULES = mctx("""
    - The budget is the one a take of the change would give at the time of the call.
        - The change's agent-running time still counts from its take.
    - The command refuses, and writes nothing, where no change closed `{fixed}` before the call has a known spend, and prints an `undecided` line on stderr.
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
    no agent id or session id."""
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
            known = bool(AGENT_ID.fullmatch(subject) or SESSION_ID.fullmatch(subject))
    if not known:
        raise Refused(mctx("`{subject}` is no `{domain}` id").format(subject=subject, domain=domain))


def file_ticket(tickets: Path, domain: str, subject: str, agent: str, text: str,
                case: list[str] | None = None) -> Path:
    """Writes `text` as a ticket of the agent's session under its first
    status, with the case `case` gives as run, start and end where it
    gives one, and returns its path."""
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
    fix = fix_field(text)
    if (case is None) != (fix is None) or (case is not None and kind is not Kind.DELAY):
        raise Refused(mctx("a `{delay}` that gives a case gives `fix`, and only then").format(
            delay=Kind.DELAY))
    status = Status.DRAFT if kind is Kind.CHANGE else Status.OPEN
    found: Case | None = None
    if case is not None and fix is not None:
        undecided: list[str] = []
        run_id, start, end = case
        found = case_loss(run_id, start, end, undecided)
        limit = None if found.dollars is None else threshold(tickets, fix, undecided)
        print_undecided(undecided)
        if found.dollars is not None and limit is not None and found.dollars < limit:
            status = Status.WATCHING
            evict(tickets, agent)
    number = reserve(tickets, session_index(tickets, session_id()))
    name = TicketName(number, dom, subject, agent).file_name
    path = write_new(tickets / status, logged(text, status, agent), [name])
    if found is not None and found.dollars is not None:
        path = log_moves(tickets, number, status, agent, status, None, found.note).moved[0]
    return path


def print_undecided(lines: list[str]) -> None:
    for line in lines:
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)


def case_command(ref: str, agent: str, run: str, start: str, end: str) -> Path:
    """Appends the case and the evidence on stdin to the watching ticket
    `ref`, and moves it to `open` where its loss reaches the threshold."""
    tickets = main_tickets()
    number = ticket_number(ref)
    path = ticket_path(tickets, number)
    if ticket_status(path) is not Status.WATCHING:
        raise Refused(mctx("{path} does not stand under `{watching}`").format(
            path=path, watching=Status.WATCHING))
    undecided: list[str] = []
    found = case_loss(run, start, end, undecided)
    path.write_text(add_evidence(read_ticket(path), sys.stdin.read()))
    if found.dollars is None:
        print_undecided(undecided)
        note = mctx("case {run} {start} {end}: cost unknown").format(run=run, start=start, end=end)
        return log_moves(tickets, number, Status.OPEN, agent, Status.WATCHING, None, note).moved[0]
    path = log_moves(tickets, number, Status.WATCHING, agent, Status.WATCHING, None,
                     found.note).moved[0]
    path = route(tickets, number, path, agent, undecided)
    print_undecided(undecided)
    return path


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
        act: Callable[..., Path | int | str], in_main: bool, argv: list[str],
        full_text: str | None = None) -> int:
    """`argv` is the call's arguments as given, which the main tree's copy
    takes in place of `args` where `in_main` holds. `full_text` is what
    `FULL_FLAG` prints, None where the call has no further rules."""
    if args and args[0] in ("--help", "-h"):
        print(help_text)
        return 0
    if args and full_text is not None and args[0] == FULL_FLAG:
        print(full_text)
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
    index = session_index(tickets, session_id())
    adopted = read_sessions(tickets, index, time.time()).adopted
    numbers = to_settle(tickets, index, adopted, map(ticket_number, given))
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


EDITORS_LINE = re.compile(r"^editors: .*$", re.MULTILINE)


def editors_command(ref: str, editor: str, agent: str, agent_id: str) -> Path:
    """Adds `editor` to the `editors` field of the held change `ref`, and
    logs the change's budget for its new `editors` set."""
    tickets = main_tickets()
    number = ticket_number(ref)
    path = ticket_path(tickets, number)
    text = read_ticket(path)
    fields = front(text)
    if ticket_kind(text) != Kind.CHANGE or ticket_status(path) is not Status.ASSIGNED:
        raise Refused(mctx("{path} is no `{change}` that stands under `{assigned}`").format(
            path=path, change=Kind.CHANGE, assigned=Status.ASSIGNED))
    given = editors_field(fields)
    added = next((r for r in EDITORS if r.value == editor), None)
    if given is None or added is None or added in given:
        raise Refused(mctx("{path} gives no `editors` field that `{editor}` is an editor to add "
                           "to").format(path=path, editor=editor))
    roles = [r for r in EDITORS if r in given or r is added]
    undecided: list[str] = []
    b = budget(tickets, frozenset(roles), time.time(), undecided)
    if b is None:
        print_undecided(undecided)
        raise Refused(mctx("the budget of {path} is unknown").format(path=path))
    names = ", ".join(map(str, roles))
    path.write_text(EDITORS_LINE.sub(f"editors: {names}", text, count=1))
    note = EDITORS_NOTE.format(editors=names, dollars=f"{b.dollars:.2f}",
                               seconds=f"{b.seconds:.0f}")
    return log_moves(tickets, number, Status.ASSIGNED, agent, Status.ASSIGNED, agent_id,
                     note).moved[0]


def show_command(*given: str) -> str:
    """The ticket `given[0]`, whole where `given` names no section, and
    otherwise its title line and each section `given[1:]` names."""
    if not given:
        raise Refused(mctx("the call gives no ticket number"))
    path = ticket_path(main_tickets(), ticket_number(given[0]))
    text = read_ticket(path)
    if len(given) == 1:
        return f"{path}\n{text.rstrip()}"
    return "\n\n".join([f"{path}\n{title_line(path, text)}",
                        *(f"{heading(name)}\n{section(text, name)}" for name in given[1:])])


def main_command(session: str) -> Path:
    tickets = main_tickets()
    name_main(tickets, session)
    return tickets / MAIN


@dataclass(frozen=True)
class Subcommand:
    """A subcommand: what it does, which its line in `HELP` and its own help
    both say, the arguments and the detail its own help adds, the rules
    that only `FULL_FLAG` prints, and how `run` runs it."""
    purpose: str
    args: str
    detail: str
    rules: str
    count: int | None
    act: Callable[..., Path | int | str]
    in_main: bool
    parse: Callable[[list[str]], Sequence[str | None]] = list


SUBCOMMANDS = {
    "log": Subcommand(mctx("makes a transition of a ticket and writes its log line"),
                      " <number> <status> <agent> --from <current status> [--id <agent id or session id>] [<note>]",
                      LOG_HELP, LOG_RULES, 6, log_command, True, log_args),
    "path": Subcommand(mctx("prints the path of a ticket"), " <number>", PATH_HELP, "", 1,
                       lambda ref: ticket_path(main_tickets(), ticket_number(ref)), False),
    "index": Subcommand(mctx("prints the index of your session"), "", "", "", 0,
                        lambda: session_index(main_tickets(), session_id()), True),
    "case": Subcommand(mctx("appends a case, with its evidence on stdin, to a watching `delay` ticket"),
                       " <number> <agent> <agent id> <start> <end>", CASE_HELP, CASE_RULES, 5, case_command, True),
    "to-settle": Subcommand(mctx("prints the open tickets an operator gives a ticket analyst to settle "
                                 "after a batch"),
                            " [<number> ...]", TO_SETTLE_HELP, TO_SETTLE_RULES, None, settle_command, False),
    "editors": Subcommand(mctx("adds an editor to a held change's `editors` field, with the "
                               "change's budget for its new `editors` set"),
                          " <number> <editor> <agent> <agent id>", EDITORS_HELP, EDITORS_RULES, 4,
                          editors_command, True),
    "main": Subcommand(mctx("sets the main session"), " <session id>", MAIN_HELP, MAIN_RULES, 1,
                       main_command, True),
    "show": Subcommand(mctx("prints a ticket, or only the sections the call names"),
                       " <number> [<section> ...]", SHOW_HELP, "", None, show_command, False),
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
                request_retired=heading(RETIRED[Kind.REQUEST]),
                statuses=ticked(Status), log=LOG, time_form=TIME_FORM,
                resolutions=ticked(Resolution), fixed=Resolution.FIXED, blocked=Status.BLOCKED,
                user=Wait.USER, change=Wait.CHANGE, validation=heading(VALIDATION),
                session_var=SESSION_VAR,
                closed_by=CLOSED_BY.format(fixed=Resolution.FIXED, change=Wait.CHANGE,
                                           number="<number>", note="<note>"),
                unblocked_by=UNBLOCKED_BY.format(change=Wait.CHANGE, number="<number>",
                                                 resolution="<resolution>"),
                sessions=SESSIONS, invocation=INVOCATION, name_form=NAME_FORM,
                question=Kind.QUESTION, refactor=Kind.REFACTOR, change_kind=Kind.CHANGE,
                change_domain=Domain.CHANGE,
                full_flag=FULL_FLAG, log_section=LOG_SECTION,
                many_ideas=MANY_IDEAS, empty=EMPTY, delay=Kind.DELAY, watching=Status.WATCHING,
                assigned=Status.ASSIGNED, open=Status.OPEN, wontfix=Resolution.WONTFIX, changes=str(CHANGES), cap=str(CAP),
                subcommands="\n".join(SUBCOMMAND_LINE.format(
                    invocation=INVOCATION, name=name, purpose=sub.purpose)
                    for name, sub in SUBCOMMANDS.items()))


def helps(call: str, render: Callable[[str], str], rules: str) -> tuple[str, str | None]:
    """The help `--help` prints, `render` given the line that names
    `FULL_FLAG` where `rules` holds any, and the help `FULL_FLAG` prints,
    `render` given `rules`, or None where `rules` holds none."""
    if not rules:
        return render("").rstrip("\n"), None
    further = FURTHER.format(call=call, full_flag=FULL_FLAG).rstrip("\n")
    return render(further).rstrip("\n"), render(rules.rstrip("\n")).rstrip("\n")


def subcommand_help(name: str, sub: Subcommand, values: dict[str, str]) -> tuple[str, str | None]:
    """The helps of `sub`, as `helps` gives them, for `<name>`."""
    def indent(text: str) -> str:
        return textwrap.indent(text.format(**values), "    ")
    return helps(f"{values['invocation']} {name}", lambda further: SUBCOMMAND_HELP.format(
        invocation=values["invocation"], name=name, args=sub.args, purpose=sub.purpose,
        detail=indent(sub.detail), further=further), indent(sub.rules))


def main(args: list[str]) -> int:
    values = help_values()
    if args[:1] and (sub := SUBCOMMANDS.get(args[0])):
        short, full = subcommand_help(args[0], sub, values)
        return run(sub.parse(args[1:]), short, sub.count, sub.act, sub.in_main, args, full)
    given: list[str | None] = list(args)
    if args[3:4] == ["--case"]:
        given = [*args[:3], " ".join(args[4:])] if len(args) == 7 else list(args)
    short, full = helps(values["invocation"], lambda further: HELP.format(**values, further=further),
                        RULES.format(**values))
    return run(given, short, 4 if len(given) == 4 else 3,
               lambda domain, subject, agent, case=None: file_ticket(
                   main_tickets(), domain, subject, agent, sys.stdin.read(),
                   None if case is None else case.split()), True, args, full)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
