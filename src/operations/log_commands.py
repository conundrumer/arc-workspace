"""The `file_ticket.py` commands the procedures print, in the form
`file_ticket.py log --help` gives."""

import shlex

from operations.roles import Role
from ticketing.vocabulary import Status

AGENT = Role.OPERATOR.value
"""The `<agent>` of each log line the operator writes."""

FILE_TICKET = ("uv", "run", "python", "scripts/file_ticket.py")


def log(number: str, status: Status, current: Status, note: str, agent_id: str | None) -> str:
    """The Bash command that moves ticket `number` from `current` to
    `status`, or writes a line in it, with `note`."""
    args = [*FILE_TICKET, "log", number, str(status),
            AGENT, "--from", str(current)]
    if agent_id is not None:
        args += ["--id", agent_id]
    return shlex.join([*args, note])


def add_editor(number: str, editor: Role, agent_id: str) -> str:
    """The Bash command that adds `editor` to the `editors` field of the
    change `number` that `agent_id` holds."""
    return shlex.join([*FILE_TICKET, "editors", number, str(editor), AGENT, agent_id])
