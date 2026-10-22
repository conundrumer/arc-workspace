"""The `editors` subcommand of `file_ticket.py`: the addition of an editor
to a held change's `editors` field, with the log line that gives the
change's budget for its new `editors` set."""

import re
import time
from pathlib import Path

from controlled_markdown import mctx
from operations.change_budget import EDITORS_NOTE, budget_fields, with_cost
from operations.roles import EDITORS
from spend_history import budget
from ticket_cases import print_undecided
from ticket_files import ticket_path, ticket_status
from ticket_form import front, ticket_kind
from ticket_log import log_moves, read_ticket
from ticket_numbers import ticket_number
from ticket_reads import design_cost, editors_field
from ticketing.vocabulary import Kind, Status
from transcript_snapshots import Refused

EDITORS_LINE = re.compile(r"^editors: .*$", re.MULTILINE)


def editors_command(tickets: Path, ref: str, editor: str, agent: str, agent_id: str) -> Path:
    """Adds `editor` to the `editors` field of the held change `ref` under
    `tickets`, and logs the change's budget for its new `editors` set."""
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
    note = EDITORS_NOTE.format(editors=names, **budget_fields(with_cost(b, design_cost(text))))
    return log_moves(tickets, number, Status.ASSIGNED, agent, Status.ASSIGNED, agent_id,
                     note).moved[0]
