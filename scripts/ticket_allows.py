"""The `allowed` subcommand of `file_ticket.py`: the tickets outside
`tickets/closed/` whose log holds an allow line, with the session ids of
those lines."""

from pathlib import Path

from controlled_markdown import mctx
from ticket_files import ticket_files, ticket_name
from ticket_log import allowers, log_lines, read_ticket
from ticketing.vocabulary import Status

ALLOWED_HELP = mctx("""
    - The command prints, for each ticket outside `tickets/{closed}/` whose log holds an allow line, as `{invocation} log --help-all` gives it, its number and then the session id of each such line, each once, one ticket per line, in the order of numbers, or `{empty}` where no ticket holds one.
    """)


def allowed_list(tickets: Path) -> list[str]:
    """The lines of `ALLOWED_HELP` for the tracker `tickets`, none where no
    ticket holds an allow line."""
    found = [(ticket_name(path).number, ids) for status in Status if status is not Status.CLOSED
             for path in ticket_files(tickets, status)
             if (ids := allowers(log_lines(read_ticket(path))))]
    return [" ".join([str(number), *ids]) for number, ids in sorted(found, key=lambda f: f[0].order)]
