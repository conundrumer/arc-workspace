"""The `case` and `sweep` subcommands of `file_ticket.py`: their help and
rules, the call that appends a case to a deferred `delay` ticket, the call
that sweeps the tickets under `tickets/deferred/`, and the routing of the
deferred groups both they and a filing with a case run.
`file_ticket.help_values` gives the values their help texts are formatted
with."""

import sys
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import ticket_path, ticket_status
from ticket_form import ticket_kind
from ticket_log import check_moves, log_moves, read_ticket
from ticket_numbers import TicketNumber, ticket_number
from ticket_sweep import sweep
from ticket_watch import Case, Thresholds, add_evidence, case_loss, route, evict
from ticketing.loss import loss
from operations.roles import Role
from ticketing.vocabulary import Kind, Status
from transcript_snapshots import Refused

CASE_HELP = mctx("""
    - `<source>` is a run id or `ticket:<number>`, and `<start>` and `<end>` bound the loss, each in the UTC form `{time_form}`.
    - Filing a `{delay}` with a case: `{invocation} <domain> <subject> <agent> --case <source> <start> <end>`.
        - The text on stdin gives `fix: <editor>` in its front matter, with the editor its fix would need among {editors}.
    - Appending a case takes the number of a `{delay}` ticket under `tickets/{deferred}/` as `<number>`.
    """)

CASE_RULES = mctx("""
    - The command records a case's dollars and its span's wall seconds in the ticket's log.
        - A run case's dollars are the token cost, in subscription dollars, of the run's requests in the span, plus the growth of the run's context across the span at the cache-read price of the run's model once for each later request of the run.
        - A ticket case's dollars are zero, and its bounds must lie within the closed source ticket's recorded life, from its first log line to its latest close.
            + xref: scripts/ticket_watch.py:case_loss
    - The loss of a case or of a change is its dollars plus its seconds at {hour_price} subscription dollars an hour, the user's $5 of list-price cost per 30 minutes converted.
    - The threshold of an editor is the median loss of the most recent {changes} `{change_kind}` tickets closed `{fixed}` with a known cost whose `editors` give that editor.
        - A change's dollars are the token cost of the runs the line that closes it gives and of the runs under them, and its seconds are the wall time those runs cover.
    - A group is the `{delay}` tickets under `tickets/{deferred}/` with one `fix` and one key: the first file path in the target of the ticket's title, the text before its first `: `, or, where the target holds none, the whole target.
    - Filing a `{delay}` with a case:
        - The ticket files under `tickets/{deferred}/` where the case's loss is below the threshold of its `fix`, and under `tickets/{new}/` otherwise.
            - Where the case's cost or the threshold is unknown, it files under `tickets/{new}/`, with an `undecided` line on stderr.
        - `tickets/{deferred}/` holds at most {cap} `{delay}` tickets.
            - A filing that would put one more there first closes `{wontfix}` each ticket of the group with the lowest loss rate, its summed loss over the days since its first case, with the group's summed loss in each note.
    - Appending a case:
        - The command adds the text on stdin to the end of the ticket's `## Evidence`, and appends the case's log line, whatever the case's own loss.
        - Where a request of the run has no price, the command moves the ticket to `tickets/{reopened}/`, and prints an `undecided` line on stderr.
    - After each filing of a `{delay}` with a case and each appended case, and before a filing closes a group `{wontfix}`, the command moves each ticket of each group whose summed loss reaches the threshold of its `fix` or passes it to `tickets/{reopened}/`, with a log line that gives the group's key, its summed loss, the threshold and the numbers of its tickets, and prints each path it went to.
        - Where the threshold of a group's `fix` is unknown, the command prints an `undecided` line on stderr, and moves the group's tickets there only where the group holds the ticket the call appends to.
    """)

SWEEP_HELP = mctx("""
    - `<agent id> ...` are the runs of the batch the last profile launch closed, and the session's operators, its operator launchers and its main run, by its session id.
    - For each `{validation_kind}` ticket under `tickets/{deferred}/`, in the order of numbers, the command checks its `{validation}` section against those runs, and moves it out of `{deferred}` where the check decides it.
    - The command then routes the `{delay}` tickets under `tickets/{deferred}/` as `{invocation} case {full_flag}` gives.
    - It prints the path of each ticket it moved, one per line, or `{none_moved}` where it moved none.
    """)

SWEEP_RULES = mctx("""
    - The command checks a `{validation_kind}` ticket only against the lines of the given runs timestamped at or after the last line of the ticket's log that moves it into `{deferred}`.
        - Where no given run holds such a line, the ticket is not exercised, whether or not its section holds an `{exercised_field}` line.
    - A ticket is exercised where one of those runs meets both conditions below.
        - Its section holds no `{agent_field}` line, or the run's agent type is one that such a line gives: `main` for a session's main run, and for a subagent's, the `agentType` of its `.meta.json`.
        - Its section holds no `{exercised_field}` line, or the pattern of one of them matches, as Python's `re.search` does, one of those lines of the run.
    - Where the ticket is exercised and its section holds a `{command_field}` line, the command runs that line's command from the main tree, for at most {seconds} seconds.
        - Where it exits 0, the ticket moves into `{closed}`, with the note `{validated} <command>`.
        - Where it exits with another code, the ticket moves into `{reopened}`, with the note `{failed}: <command> exited <code>`, and where it runs past the time, with the note `{failed}: <command> timed out`.
    - Where the ticket is exercised and its section holds no `{command_field}` line, it moves into `{reopened}`, with the note `{exercised}: <agent id> ...`, with the runs that meet both conditions.
    - Where the ticket is not exercised, and the last line of its log that moves it into `{deferred}` is {days} days old or more, it moves into `{reopened}`, with the note `{unexercised}: no run matched since <time>`, with that line's time.
    - Where a ticket's section holds more than one `{command_field}` line, or a pattern that does not compile or that the `{exercised_field}` line of `{invocation} --help` gives the sweep as refusing, or where its log holds no line that moves it into `{deferred}`, it moves into `{reopened}`, with the note `{failed}: <reason>`.
    - Where running the command of a `{command_field}` line would take the sweep past the timeout of a foreground Bash call, the command does not start it, and the ticket stays in `{deferred}` until the next sweep, with an `undecided` line on stderr.
    - The command refuses, and moves nothing, where a run it gives has no transcript.
    """)

NONE_MOVED = mctx("no ticket moved")


def routed(tickets: Path, agent: str, limits: Thresholds,
           own: TicketNumber | None) -> Path | None:
    """Routes each deferred group as `route` does, prints the path each
    moved ticket other than `own` went to, and returns the path `own` went
    to, or None where the routing leaves it in place."""
    moved = route(tickets, agent, limits, own)
    for other, to in moved.items():
        if other != own:
            print(to)
    return None if own is None else moved.get(own)


def print_undecided(lines: list[str]) -> None:
    for line in lines:
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)


def case_command(tickets: Path, ref: str, agent: str, run: str, start: str,
                 end: str) -> Path:
    """Appends the case and the evidence on stdin to the deferred `delay`
    ticket `ref` of the tracker `tickets`, and routes each deferred group
    as `route` does; where its log line would be refused, it writes
    nothing."""
    number = ticket_number(ref)
    path = ticket_path(tickets, number)
    if ticket_status(path) is not Status.DEFERRED or ticket_kind(read_ticket(path)) is not Kind.DELAY:
        raise Refused(mctx("{path} is no `{delay}` that stands under `{deferred}`").format(
            path=path, delay=Kind.DELAY, deferred=Status.DEFERRED))
    undecided: list[str] = []
    found = case_loss(run, start, end, undecided, tickets)
    if found.dollars is None:
        status = Status.REOPENED
        note = mctx("case {run} {start} {end}: cost unknown").format(run=run, start=start, end=end)
    else:
        status, note = Status.DEFERRED, found.note
    check_moves(tickets, number, status, agent, Status.DEFERRED, None, note)
    path.write_text(add_evidence(read_ticket(path), sys.stdin.read()))
    path = log_moves(tickets, number, status, agent, Status.DEFERRED, None, note).moved[0]
    path = routed(tickets, agent, Thresholds(tickets, undecided), number) or path
    print_undecided(undecided)
    return path


def sweep_command(tickets: Path, *runs: str) -> str:
    """Runs `sweep` on the tracker `tickets` and the runs `runs`, and
    returns the paths it moved tickets to, one per line."""
    undecided: list[str] = []
    moved = sweep(tickets, list(runs), undecided)
    print_undecided(undecided)
    return "\n".join(map(str, moved)) if moved else NONE_MOVED


def filing_case(tickets: Path, agent: str, case: list[str], fix: Role,
                limits: Thresholds, undecided: list[str]) -> tuple[Case, Status]:
    """Price and route a filing's case before its ticket is written."""
    source, start, end = case
    found = case_loss(source, start, end, undecided, tickets)
    limit = None if found.dollars is None else limits(fix)
    status = Status.NEW
    if (found.dollars is not None and limit is not None
            and loss(found.dollars, found.seconds) < limit):
        status = Status.DEFERRED
        routed(tickets, agent, limits, None)
        evict(tickets, agent)
    return found, status
