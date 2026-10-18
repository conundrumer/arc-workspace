"""The `log` subcommand of `file_ticket.py`: its help, its rules, the
parse of its arguments, and the call that makes a ticket's transition and
writes its log line. `file_ticket.help_values` gives the values its help
texts are formatted with."""

from pathlib import Path

from controlled_markdown import mctx
from ticket_log import log_moves, status_of
from ticket_numbers import ticket_number
from ticketing.vocabulary import Status
from transcript_entries import Refused

LOG_HELP = mctx("""
    - `<status>` and `<current status>` are each one of {statuses}.
        - `<current status>` is the status you saw the ticket in.
    - A line that moves a ticket into `assigned` takes, in `--id`, the agent id of the agent that writes it, or the session id of a session that writes it for itself or that an operator hands a change to.
    - The note of a line that moves a ticket into `{blocked}` or `{waiting}` opens with what the ticket waits on: `{user}` into `{blocked}`, and `{change} <number>` into `{waiting}`, with `<number>` the number of a `change` ticket the ticket tracker holds.
    - A ticket waits on the change that the last line of its log whose note opens with what a ticket waits on gives as `{change} <number>`.
    - The note of a line that moves a ticket into `closed` opens with its resolution, one of {resolutions}.
        - With `{duplicate}`, the note has the form `{duplicate_of}`, with `<number>` the number of the ticket it duplicates.
    - A line whose note opens with `{recurs} <number>` records a recurrence of the defect the ticket records, with `<number>` the number of a `{bug}` whose root cause is that defect.
    """)

LOG_RULES = mctx("""
    - The ticket is the one with that number, and the command prints its path.
    - The command refuses, and neither moves nor writes, where the ticket stands in another status than `<current status>`, or where its file moves before the command moves it.
    - Where `<status>` differs from `<current status>`, the command moves the ticket's file to the directory of `<status>`.
    - A line that moves a ticket into `closed`, with a note that opens with `{fixed}` and not with `{validated}`, acts on a ticket of these kinds as follows, and so does each line below that moves a ticket that waits on a change:
        - A `{request}` that holds a `{validation}` section moves into `closed`, and the command moves that section into a new `{validation_kind}` ticket, whose `{validates}` field gives the request's number, which it writes under `tickets/{deferred}/`, and prints that ticket's path after the request's.
        - A `{validation_kind}` ticket moves into `{deferred}` in place of `closed`, with the same note, and waits there on its check, as `{invocation} sweep --help-all` gives.
    - The command appends `<time> <status> [<agent>]: <note>` to the file's `{log}`, with the time in UTC in the form `{time_form}`, and with `<agent> <id>` in the bracket where `--id` gives an id.
        - `--id` takes an agent id, or the session id `$CLAUDE_CODE_SESSION_ID` holds.
        - A line with no `<note>` ends at the bracket.
    - On a ticket that already stands in `assigned`, the command refuses an `assigned` line whose `--id` does not hold the ticket, and accepts one with no `--id`.
        - The holder is the agent id or the session id of the last `assigned` line that gives one, in its bracket or as the first word of its note, among the log's final run of `assigned` lines.
            - Where none of them gives one, the ticket has no holder.
    - Where the line moves a `{change}` ticket into `closed`, the command also moves each ticket under `{waiting}` that waits on that change, and prints the path of each one it moved, one per line, after the change's own path.
    - A `{change}` ticket that waits on it moves into `open`, with the note `{unblocked_by}`, whatever the change's resolution.
    - Each other ticket that waits on it, where the change's resolution is `{fixed}` and a `{change}` outside `tickets/{closed}/` gives the ticket's number in its `Motivation`, stays under `{waiting}` and waits on the lowest-numbered such change, `<next>`, with the note `{waits_on_next}`.
    - Each other ticket that waits on it, where the change's resolution is `{fixed}` and no such change stands, moves into `closed`, with the note `{closed_by}`.
    - Each other ticket that waits on it, where the change's resolution is another, moves into `open`, with the note `{unblocked_by}`.
    - Each line that moves a ticket that waits on the change takes the `<agent>` and the `--id` of the call.
    - A ticket that waits on the change and that another call moves first, the command skips.
    - The command moves those tickets in the order of their file names.
        - Where the move of one is refused for another reason, the command moves the others, prints the path of each ticket it moved, and then refuses, with the change's path and the path of each ticket it did not move, with the reason.
    - The command refuses, and neither moves nor writes, where the line moves a `{request}` that holds a `{validation}` section into `{waiting}` from another status, and the sweep refuses the check that section gives, as `{invocation} sweep --help-all` gives, and gives the sweep's reason.
    - The command refuses, and neither moves nor writes, where `{log}` is not the file's last section or the note spans more than one line.
    - The command refuses, and neither moves nor writes, where the line leaves the ticket on a cycle of links, as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) defines a link, among the tickets outside `tickets/{closed}/`, and gives the tickets of the shortest such cycle in order, unless the line moves the ticket into `{closed}`, or into `draft` from another status.
        + xref: prompts/agents/notes/tickets.md#change-tickets
    """)


def log_args(args: list[str]) -> list[str | None]:
    """The arguments of `log` as `log_command` takes them, as text,
    with None for an agent id or a note the call does not give. Arguments
    in another form come back as given, which `file_ticket.run` refuses by their
    count."""
    head, rest = args[:3], args[3:]
    options: dict[str, str] = {}
    while rest[:1] in (["--from"], ["--id"]) and len(rest) >= 2 and rest[0] not in options:
        options[rest[0]] = rest[1]
        rest = rest[2:]
    if len(head) < 3 or "--from" not in options or len(rest) > 1 or rest[:1] in (["--from"], ["--id"]):
        return list(args)
    return [*head, options["--from"], options.get("--id"), rest[0] if rest else None]


def log_command(tickets: Path, ref: str, status: str, agent: str, source: str, agent_id: str | None,
                note: str | None) -> str:
    """Runs `log_moves` on the tracker `tickets` and returns the paths it moved tickets to, one per
    line. Where it gives a refused ticket, prints those paths, then refuses
    with the change's path and each refused ticket's path and reason."""
    moves = log_moves(tickets, ticket_number(ref), status_of(status), agent, status_of(source),
                      agent_id, note)
    paths = "\n".join(map(str, moves.moved))
    if not moves.refused:
        return paths
    print(paths)
    refused = "; ".join(f"{p}: {reason}" for p, reason in moves.refused)
    raise Refused(mctx("{path} moved into `{closed}`, and these tickets that wait on it did not move: "
                       "{refused}").format(path=moves.moved[0], closed=Status.CLOSED, refused=refused))
