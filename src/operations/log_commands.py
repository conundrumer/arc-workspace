"""The `file_ticket.py` commands the procedures print, in the form
`file_ticket.py log --help` gives, and the step that files a ticket
(`file_ticket`)."""

import shlex

from operations.roles import Role
from operations.steps import Bash
from ticketing.vocabulary import Domain, Status

AGENT = Role.OPERATOR.value
"""The `<agent>` of each log line the operator writes."""

FILE_TICKET = ("uv", "run", "python", "scripts/file_ticket.py")


def file_ticket(domain: Domain, subject: str, text: str, about: str, *, occasion: str,
                retires: str | None = None) -> Bash:
    """The Bash step that files the ticket whose text is `text`, on
    `subject` of `domain`, with `about`, `occasion` and `retires` as
    `steps.Bash` gives them."""
    return Bash(shlex.join([*FILE_TICKET, domain.value, subject, AGENT])
                + " <<'TICKET'\n" + text + "TICKET", about, retires=retires, occasion=occasion)


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
