"""File a ticket under the main tree's `tickets/`, from the main tree or any
worktree of it, print a ticket's path, make a ticket's transitions and
write its log lines, sweep the tickets under `tickets/deferred/`, list
the untaken tickets a ticket analyst settles and the tickets the coordinator
allowed, print a ticket or the sections
of it a reader names, and wait for a ticket to close. The `HELP` of
`filing_help`, which `--help` prints, says how an agent files, `--help
PART` prints the form of a kind, and each subcommand's own help, which its
`--help` prints, how an agent calls it. `--help-all` prints a help with
the forms and the rules a well-formed call does not need, from `FORMS`
and `RULES` and each subcommand's `rules`."""

import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from operations.roles import EDITORS
from engine import checkout
from handbook.paths import scripts_importable

scripts_importable()

from ticket_files import FIELD, NAME_FORM, TicketName, ticket_path, ticket_status  # noqa: E402
from ticket_paths import SCOPE, section_paths  # noqa: E402
from ticket_citations import (CITING_HELP, CLOSED_ON_HELP, EMPTY,  # noqa: E402
                              citing_command, closed_on_command)
from tree_reads import main_tree, run_in_main  # noqa: E402
from ticket_form import (DESIGN, FormRefused, LOG, LOG_SECTION, MECHANICAL,  # noqa: E402
                         RETIRED, VALIDATES, checked_kind, section, sections_example,
                         title_line)
from ticket_log import (CLOSED_BY, DUPLICATE_OF, UNBLOCKED_BY, VALIDATED,  # noqa: E402
                        WAITS_ON_NEXT, Wait, log_lines, log_moves, logged, read_ticket, resolution_of)
from ticket_log_command import LOG_HELP, LOG_RULES, log_args, log_command  # noqa: E402
from ticket_numbers import (SESSION_VAR, SESSIONS, TicketNumber, reserve, session_id,  # noqa: E402
                            session_index, ticket_number, write_new)
from ticket_settle import to_settle  # noqa: E402
from ticket_allows import ALLOWED_HELP, allowed_list  # noqa: E402
from ticket_subjects import filed_subject  # noqa: E402
from idle_sessions import MAIN, name_main, read_sessions  # noqa: E402
from ticket_editors import editors_command  # noqa: E402
from ticket_watch import (CAP, CHANGES, Case,  # noqa: E402
                          Thresholds, case_loss, evict, fix_field)
from ticket_sweep import (AGENT_FIELD, COMMAND_FIELD, COMMAND_SECONDS, EXERCISED_FIELD,  # noqa: E402
                          UNEXERCISED_DAYS)
from ticketing.loss import SECOND_PRICE, loss  # noqa: E402
from ticketing.text import SECTIONS, VALIDATION, heading  # noqa: E402
from ticketing.times import TIME_FORM  # noqa: E402
from ticket_vocabulary import ticked  # noqa: E402
from ticketing.vocabulary import (ALLOW, DEFECT_SECTIONS, MANY_IDEAS, UNTAKEN, Domain, Kind,  # noqa: E402
                                  Note, Resolution, Status, Verdict, queued)
from transcript_snapshots import Refused, print_refused  # noqa: E402
from filing_help import FORM_PURPOSES, FORMS, HELP, RULES, FormPart  # noqa: E402
from help_parts import part_lines, print_help  # noqa: E402
from ticket_cases import (filing_case, CASE_HELP, CASE_RULES, NONE_MOVED, SWEEP_HELP, SWEEP_RULES,  # noqa: E402
                          case_command, print_undecided, routed, sweep_command)

HELP_RETRY = mctx("{reason}: run `{call} --help{part}`")
"""The refusal of a call, with the help that gives the form the call
misses: `part` is empty, or a space and the part of the help."""

SUBCOMMAND_LINE = mctx("""
    - `{name}` {purpose}: `{invocation} {name} --help` prints its form.
    """)

SUBCOMMAND_HELP = mctx("""
    - `{call}{args}` {purpose}.
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

TO_SETTLE_HELP = mctx("""
    - The list holds each ticket that stands in one of {queue} that your session filed or whose number the call gives.
        - Where your session is the main session, as `{invocation} main --help` defines it, the list also holds each ticket that stands in one of {queue} that a session in which no agent runs filed.
    - The command prints the number of each ticket the list holds, one per line, in the order of numbers, or `{empty}` where it holds none.
    """)

TO_SETTLE_RULES = mctx("""
    - The list leaves out each `{change_kind}`, each `{question}` filed on a change whose ticket stands outside `tickets/closed/`, each `{refactor}` whose title ends in `{many_ideas}`, and each ticket whose `depends-on` gives a ticket that stands outside `tickets/closed/`.
    - A `{question}` with the `<domain>` `{change_domain}` is filed on the change its `<subject>` gives.
    - The command refuses where a number the call gives names no ticket, where the front matter of a ticket the list would hold gives no kind, where a `{refactor}` it would hold has no title, or where a `{question}` filed on a change, or a `depends-on` entry of a ticket it would hold, names no ticket the ticket tracker holds.
    """)

MAIN_HELP = mctx("""
    - The main session is the one whose operators act on the tickets of each other session in which no agent runs as on its own.
    - `<session id>` is the id of the session the user picks.
    """)

MAIN_RULES = mctx("""
    - The command writes `<session id>` to `tickets/main`, in place of what it holds, and removes `tickets/main-wanted`, the mark that a session has asked the user to pick a main session.
    - Where `tickets/main` holds no session id, or the id of a session whose process has ended, the first session to read it, by its machine watcher or by its operator, writes its own id there, and is the main session until this command sets another.
    """)

SHOW_HELP = mctx("""
    - The command prints the ticket's path and its title line, and then each named section, from its heading to the next heading, in the order the call names them.
        - Where the call names no section, it prints the path and then the whole ticket.
    - A `<section>` is the text of a heading after its mark, as `{log_section}` for `{log}`.
    """)

AWAIT_CLOSE_HELP = mctx("""
    - Run it in the background: its completion notification gives what it prints.
    - The command ends once a ticket the call gives stands under `tickets/{closed}/`, and prints, for each ticket that stands there, its number and the log line that closed it.
    """)

AWAIT_CLOSE_INTERVAL = 10
"""The seconds between two reads of where the waited tickets stand."""

EDITORS_HELP = mctx("""
    - `<number>` is the number of a `{change_kind}` ticket that stands under `tickets/{assigned}/`, `<editor>` one of {editors} that its `editors` field does not give, and `<agent id>` the holder of the ticket.
    - The command adds `<editor>` to the ticket's `editors` field, appends a log line with the budget of the change for its new `editors` set, and prints the ticket's path.
    """)

EDITORS_RULES = mctx("""
    - The budget is the one a take of the change would give at the time of the call.
        - The change's agent-running time still counts from its take.
    - The command refuses, and writes nothing, where no change closed `{fixed}` before the call has a known spend, and prints an `undecided` line on stderr.
    """)

GROUND_HELP = mctx("""
    - `<path>:<first>-<last>` is a file from the root of the tree, and the first and the last line of a span of it, from 1.
    - The command prints the `{grounds}` line of that span, as the file stands at `master`: its path and span in backticks, the hash of `master`, and the span's lines, each with no indent, joined by spaces, in quotes.
    - With `--command`, it runs `<command>` with the shell in the main tree, for at most {ground_seconds} seconds, and prints the `{grounds}` line of the command: the command in backticks, the hash of `master`, its exit code where it is not 0, and its output and its errors, in a fence under that line, or that it prints nothing.
    """)

GROUND_SPAN = mctx('- `{path}:{first}-{last}` (master {hash}): "{quote}"')
GROUND_COMMAND = mctx("- `{command}` (master {hash}){exits} prints:")
GROUND_SILENT = mctx("- `{command}` (master {hash}){exits} prints nothing.")
GROUND_EXITS = mctx(", exits {code},")

GROUND_SECONDS = 200

SPAN = re.compile(r"(?P<path>[^:\s]+):(?P<first>[1-9]\d*)-(?P<last>[1-9]\d*)")

SCOPE_CHECK_HELP = mctx("""
    - `<number>` is the number of a `{change_kind}` ticket. With no `<number>`, the command reads the text of a draft on its stdin, in the form a filing takes: `{invocation} scope-check <<'EOF'`, the text, and `EOF`.
    - The command prints each path the ticket's `{design}` gives that its `{scope}` gives neither as a path nor as a directory that holds it, one per line, or `{covered}` where none.
        - The paths a section gives are those `uv run python scripts/file_ticket.py --help-all` gives.
    - It exits 0 whatever it prints, so judge each path it prints: a path the `{design}` cites and the change does not edit stays out of the Scope.
    """)

COVERED = mctx("the Scope covers each path the Design gives")


def file_ticket(tickets: Path, domain: str, subject: str, agent: str, text: str,
                case: list[str] | None = None, filed: str = Note.FILED) -> Path:
    """Writes `text` as a ticket of the agent's session under its first
    status, with the case `case` gives as source, start and end where it
    gives one, and the note `filed` on the line that files it, and returns
    its path."""
    try:
        dom = Domain(domain)
    except ValueError:
        raise Refused(mctx("`{domain}` is no domain: the domains are {domains}").format(
            domain=domain, domains=ticked(Domain)))
    if not FIELD.fullmatch(agent):
        raise Refused(mctx("`{agent}` is not kebab words").format(agent=agent))
    kind = checked_kind(tickets, agent, text)
    subject = filed_subject(tickets, kind, dom, subject)
    fix = fix_field(text)
    if (case is None) != (fix is None) or (case is not None and kind is not Kind.DELAY):
        raise Refused(mctx("a `{delay}` that gives a case gives `fix`, and only then").format(
            delay=Kind.DELAY))
    status = Status.DRAFT if kind is Kind.CHANGE else queued(None, kind)
    found: Case | None = None
    undecided: list[str] = []
    limits = Thresholds(tickets, undecided)
    if case is not None and fix is not None:
        found, status = filing_case(tickets, agent, case, fix, limits, undecided)
    number = reserve(tickets, session_index(tickets, session_id()))
    name = TicketName(number, dom, subject, agent).file_name
    path = write_new(tickets / status, logged(text, status, agent, filed), [name])
    if found is not None and found.dollars is not None:
        path = log_moves(tickets, number, status, agent, status, None, found.note).moved[0]
    if found is not None:
        path = routed(tickets, agent, limits, number) or path
    print_undecided(undecided)
    return path


def main_tickets() -> Path:
    return main_tree() / "tickets"


SCRIPT = "file_ticket.py"

INVOCATION = f"uv run python scripts/{SCRIPT}"
"""The command that runs this script, as a help text writes it."""


class ArgumentsRefused(Refused):
    """A refusal of a call's arguments, which `run` completes with the
    pointer to the `--help` of the call."""


@dataclass(frozen=True)
class Call:
    """A call `run` runs: `invocation` is that of the command or subcommand,
    `argv` the call's arguments as given, which the main tree's copy takes
    in place of the parsed arguments where `in_main` holds, and `full_text`
    what `FULL_FLAG` prints, None where the call has no further rules."""
    invocation: str
    argv: list[str]
    help_text: str
    count: int | None
    act: Callable[..., Path | int | str]
    in_main: bool
    full_text: str | None = None


def run(args: Sequence[str | None], call: Call) -> int:
    if args and args[0] in ("--help", "-h"):
        print(call.help_text)
        return 0
    if args and call.full_text is not None and args[0] == FULL_FLAG:
        print(call.full_text)
        return 0
    if call.count is not None and len(args) != call.count:
        print(call.help_text, file=sys.stderr)
        return 2
    try:
        status = run_in_main(SCRIPT, call.argv) if call.in_main else None
        if status is not None:
            return status
        print(call.act(*args))
    except ArgumentsRefused as e:
        print_refused(HELP_RETRY.format(reason=e, call=call.invocation, part=""))
        return 1
    except FormRefused as e:
        print_refused(HELP_RETRY.format(reason=e, call=call.invocation,
                                        part="" if e.part is None else f" {e.part}"))
        return 1
    except Refused as e:
        print_refused(e)
        return 1
    return 0


def settle_command(*given: str) -> str:
    tickets = main_tickets()
    session = session_id()
    index = session_index(tickets, session)
    adopted = read_sessions(tickets, index, session, time.time()).adopted
    numbers = to_settle(tickets, index, adopted, map(ticket_number, given))
    return "\n".join(map(str, numbers)) if numbers else EMPTY


def show_command(*given: str) -> str:
    """The ticket `given[0]`, whole where `given` names no section, and
    otherwise its title line and each section `given[1:]` names."""
    if not given:
        raise ArgumentsRefused(mctx("the call gives no ticket number"))
    path = ticket_path(main_tickets(), ticket_number(given[0]))
    text = read_ticket(path)
    if len(given) == 1:
        return f"{path}\n{text.rstrip()}"
    return "\n\n".join([f"{path}\n{title_line(path, text)}",
                        *(f"{heading(name)}\n{section(text, name)}" for name in given[1:])])


def await_close_command(*given: str) -> str:
    """Each ticket of `given` that stands under `closed`, with the line of
    its log that closed it, once one does."""
    if not given:
        raise ArgumentsRefused(mctx("the call gives no ticket number"))
    tickets = main_tickets()
    numbers = [ticket_number(ref) for ref in given]
    for number in numbers:
        ticket_path(tickets, number)
    while True:
        closed = [(n, p) for n in numbers
                  if ticket_status(p := ticket_path(tickets, n)) is Status.CLOSED]
        if closed:
            return "\n".join(f"{n}: {closing_line(p)}" for n, p in closed)
        time.sleep(AWAIT_CLOSE_INTERVAL)


def closing_line(path: Path) -> str:
    """The last log line of the ticket at `path` whose note opens with a
    resolution: a line appended after the close, such as a correction,
    gives none."""
    lines = [m for m in log_lines(read_ticket(path))
             if m["status"] == Status.CLOSED and resolution_of(m["note"]) is not None]
    if not lines:
        raise Refused(mctx("{path} has no log line that closes it with a resolution").format(path=path))
    return lines[-1].group()


def named(command: Callable[[Sequence[str]], str]) -> Callable[..., str]:
    """`command` as the act of a subcommand that takes one or more names,
    which refuses a call that gives none."""
    def act(*given: str) -> str:
        if not given:
            raise ArgumentsRefused(mctx("the call gives no name"))
        return command(given)
    return act


def master_hash(main: Path) -> str:
    return checkout.git_out(main, "rev-parse", "--short=8", "master").strip()


def ground_command(*given: str) -> str:
    """The `Grounds` line of the span or of the command `given` gives, as
    `GROUND_HELP` gives it."""
    main = main_tree()
    if len(given) == 2 and given[0] == "--command":
        try:
            done = subprocess.run(given[1], shell=True, cwd=main, capture_output=True, text=True,
                                  timeout=GROUND_SECONDS)
        except subprocess.TimeoutExpired:
            raise Refused(mctx("`{command}` ran past {seconds} seconds: give its Grounds line by hand").format(
                command=given[1], seconds=GROUND_SECONDS))
        exits = "" if done.returncode == 0 else GROUND_EXITS.format(code=done.returncode)
        out = (done.stdout + done.stderr).rstrip("\n")
        values = dict(command=given[1], hash=master_hash(main), exits=exits)
        if not out:
            return GROUND_SILENT.format(**values)
        return f"{GROUND_COMMAND.format(**values)}\n{textwrap.indent(f'```\n{out}\n```', '    ')}"
    span = SPAN.fullmatch(given[0]) if len(given) == 1 else None
    if span is None:
        raise ArgumentsRefused(mctx("the call gives neither `<path>:<first>-<last>` nor `--command <command>`"))
    first, last = int(span["first"]), int(span["last"])
    shown = checkout.git(main, "show", f"master:{span['path']}")
    lines = shown.stdout.splitlines()
    if shown.returncode != 0 or not first <= last <= len(lines):
        raise ArgumentsRefused(mctx("`master` holds no file `{path}` with lines {first} to {last}").format(
            path=span["path"], first=first, last=last))
    quote = " ".join(line.strip() for line in lines[first - 1:last])
    return GROUND_SPAN.format(path=span["path"], first=first, last=last, hash=master_hash(main), quote=quote)


def scope_check_command(*given: str) -> str:
    """The paths of a ticket's `Design` that its `Scope` does not cover, as
    `SCOPE_CHECK_HELP` gives them."""
    if len(given) > 1:
        raise ArgumentsRefused(mctx("the call gives more than one number"))
    text = read_ticket(ticket_path(main_tickets(), ticket_number(given[0]))) if given else sys.stdin.read()
    root = main_tree()
    scope = section_paths(text, SCOPE, root)
    missing = sorted(p for p in section_paths(text, DESIGN, root)
                     if not any(Path(p).is_relative_to(s) for s in scope))
    return "\n".join(missing) if missing else COVERED


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
                      LOG_HELP, LOG_RULES, 6,
                      lambda *given: log_command(main_tickets(), *given), True, log_args),
    "path": Subcommand(mctx("prints the path of a ticket"), " <number>", PATH_HELP, "", 1,
                       lambda ref: ticket_path(main_tickets(), ticket_number(ref)), False),
    "index": Subcommand(mctx("prints the index of your session"), "", "", "", 0,
                        lambda: session_index(main_tickets(), session_id()), True),
    "case": Subcommand(mctx("appends a case, with its evidence on stdin, to a deferred `delay` ticket"),
                       " <number> <agent> <source> <start> <end>", CASE_HELP, CASE_RULES, 5,
                       lambda *given: case_command(main_tickets(), *given), True),
    "sweep": Subcommand(mctx("moves each `validation` ticket under `tickets/deferred/` whose check decides it, "
                             "and each `delay` there whose group reaches its threshold"),
                        " [<agent id> ...]", SWEEP_HELP, SWEEP_RULES, None,
                        lambda *given: sweep_command(main_tickets(), *given), True),
    "to-settle": Subcommand(mctx("prints the untaken tickets an operator gives a ticket analyst to settle "
                                 "after a batch"),
                            " [<number> ...]", TO_SETTLE_HELP, TO_SETTLE_RULES, None, settle_command, False),
    "allowed": Subcommand(mctx("prints the tickets the coordinator allowed, with the session ids of "
                               "their allow lines"),
                          "", ALLOWED_HELP, "", 0,
                          lambda: "\n".join(allowed_list(main_tickets())) or EMPTY, False),
    "editors": Subcommand(mctx("adds an editor to a held change's `editors` field, with the "
                               "change's budget for its new `editors` set"),
                          " <number> <editor> <agent> <agent id>", EDITORS_HELP, EDITORS_RULES, 4,
                          lambda *given: editors_command(main_tickets(), *given), True),
    "main": Subcommand(mctx("sets the main session"), " <session id>", MAIN_HELP, MAIN_RULES, 1,
                       main_command, True),
    "show": Subcommand(mctx("prints a ticket, or only the sections the call names"),
                       " <number> [<section> ...]", SHOW_HELP, "", None, show_command, False),
    "await-close": Subcommand(mctx("ends once a ticket closes, and prints how it closed"),
                              " <number> [<number> ...]", AWAIT_CLOSE_HELP, "", None, await_close_command, False),
    "closed-on": Subcommand(mctx("prints the closed tickets whose title refers to a target, with how each closed"),
                            " <name> [<name> ...]", CLOSED_ON_HELP, "", None, named(closed_on_command), False),
    "citing": Subcommand(mctx("prints, for each name, the tickets of any status whose title refers to it, "
                              "with the status, the kind and the last log line of each"),
                         " <name> [<name> ...]", CITING_HELP, "", None, named(citing_command), False),
    "ground": Subcommand(mctx("prints the `Grounds` line of a span of a file or of a command"),
                         " <path>:<first>-<last> | --command <command>", GROUND_HELP, "", None,
                         ground_command, False),
    "scope-check": Subcommand(mctx("prints each path a change's `Design` gives that its `Scope` does not"),
                              " [<number>]", SCOPE_CHECK_HELP, "", None, scope_check_command, False),
}
"""Each subcommand, by the word that calls it, in the order `HELP` gives
their lines."""


def help_values() -> dict[str, str]:
    """The values each help text of `file_ticket.py` is formatted with."""
    return dict(domains=ticked(Domain), editors=ticked(map(str, EDITORS)),
                mechanical=MECHANICAL,
                defect_sections=sections_example(DEFECT_SECTIONS),
                defect_headings=ticked(map(heading, DEFECT_SECTIONS)),
                change_sections=ticked(map(heading, SECTIONS[Kind.CHANGE])), design=heading(DESIGN),
                request_sections=ticked(map(heading, SECTIONS[Kind.REQUEST])),
                request_retired=heading(RETIRED[Kind.REQUEST]),
                statuses=ticked(Status), log=LOG, time_form=TIME_FORM,
                resolutions=ticked(Resolution), fixed=Resolution.FIXED, blocked=Status.BLOCKED,
                waiting=Status.WAITING,
                user=Wait.USER, change=Wait.CHANGE, validation=heading(VALIDATION),
                session_var=SESSION_VAR,
                duplicate=Resolution.DUPLICATE, recurs=Note.RECURS, bug=Kind.BUG,
                duplicate_of=DUPLICATE_OF.format(duplicate=Resolution.DUPLICATE, number="<number>",
                                                 note="<note>"),
                closed_by=CLOSED_BY.format(fixed=Resolution.FIXED, change=Wait.CHANGE,
                                           number="<number>", note="<note>"),
                unblocked_by=UNBLOCKED_BY.format(change=Wait.CHANGE, number="<number>",
                                                 resolution="<resolution>"),
                waits_on_next=WAITS_ON_NEXT.format(change=Wait.CHANGE, next="<next>",
                                                   number="<number>", resolution=Resolution.FIXED),
                sessions=SESSIONS, invocation=INVOCATION, name_form=NAME_FORM,
                question=Kind.QUESTION, refactor=Kind.REFACTOR, change_kind=Kind.CHANGE,
                change_domain=Domain.CHANGE,
                full_flag=FULL_FLAG, log_section=LOG_SECTION,
                many_ideas=MANY_IDEAS, empty=EMPTY, delay=Kind.DELAY, deferred=Status.DEFERRED, request=Kind.REQUEST,
                validation_kind=Kind.VALIDATION, validates=VALIDATES,
                validated=VALIDATED, failed=Verdict.FAILED, exercised=Verdict.EXERCISED,
                unexercised=Verdict.UNEXERCISED, days=str(UNEXERCISED_DAYS),
                seconds=str(COMMAND_SECONDS), exercised_field=EXERCISED_FIELD,
                command_field=COMMAND_FIELD, agent_field=AGENT_FIELD, none_moved=NONE_MOVED,
                assigned=Status.ASSIGNED, closed=Status.CLOSED,
                new=Status.NEW, approved=Status.APPROVED, reopened=Status.REOPENED, released=Status.RELEASED,
                queue=ticked(UNTAKEN), allow=ALLOW, wontfix=Resolution.WONTFIX, changes=str(CHANGES), cap=str(CAP),
                hour_price=f"{SECOND_PRICE * 3600:g}",
                grounds=SECTIONS[Kind.CHANGE][-1], ground_seconds=str(GROUND_SECONDS), scope=heading(SCOPE), covered=COVERED,
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


def subcommand_help(call: str, sub: Subcommand, values: dict[str, str]) -> tuple[str, str | None]:
    """The helps of `sub`, as `helps` gives them, for the invocation `call`."""
    def indent(text: str) -> str:
        return textwrap.indent(text.format(**values), "    ")
    return helps(call, lambda further: SUBCOMMAND_HELP.format(
        call=call, args=sub.args, purpose=sub.purpose,
        detail=indent(sub.detail), further=further), indent(sub.rules))


def main(args: list[str]) -> int:
    values = help_values()
    if args[:1] and (sub := SUBCOMMANDS.get(args[0])):
        call = f"{values['invocation']} {args[0]}"
        short, full = subcommand_help(call, sub, values)
        return run(sub.parse(args[1:]), Call(call, args, short, sub.count, sub.act, sub.in_main, full))
    given: list[str | None] = list(args)
    if args[3:4] == ["--case"]:
        given = [*args[:3], " ".join(args[4:])] if len(args) == 7 else list(args)
    invocation, rules = values["invocation"], RULES.format(**values)

    def filing(parts: str) -> Callable[[str], str]:
        return lambda further: HELP.format(**values, parts=parts, further=further)
    if args[:1] in (["--help"], ["-h"]):
        return print_help(args[1:], FormPart, lambda parts: helps(invocation, filing(parts), rules)[0],
                          FORM_PURPOSES, lambda part: FORMS[part].format(**values))
    short = helps(invocation, filing(part_lines(FormPart, FORM_PURPOSES)), rules)[0]
    full = helps(invocation, filing("\n".join(FORMS[p].format(**values).rstrip("\n") for p in FormPart)),
                 rules)[1]
    return run(given, Call(invocation, args, short, 4 if len(given) == 4 else 3,
                           lambda domain, subject, agent, case=None: file_ticket(
                               main_tickets(), domain, subject, agent, sys.stdin.read(),
                               None if case is None else case.split()), True, full))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
