"""The check of the subject a filing gives a ticket, against the ticket's
kind and domain: the form of the subject of a ticket that asks for a
change, and the id of a thing of the domain for every other kind."""

import re
from pathlib import Path

from arc.task import task_file
from controlled_markdown import mctx
from engine import checkout
from ticket_files import FIELD, ticket_path
from ticket_log import AGENT_ID, SESSION_ID
from ticket_numbers import parsed_number, ticket_number
from ticketing.vocabulary import Domain, Kind
from transcript_snapshots import Refused

COMMIT = re.compile(r"[0-9a-f]{7,40}")

CHANGE_SUBJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
"""The subject of a ticket that asks for a change: its namespace, then
kebab words. A ticket number (`ticket_numbers.parsed_number`) is no such
subject."""

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


def filed_subject(tickets: Path, kind: Kind, domain: Domain, subject: str) -> str:
    """The subject a ticket of `kind` and `domain` is filed under, given
    `subject`, which for a ticket that asks for a change has each `_` read
    as `-`; or a refusal where it is not kebab words, where a ticket that
    asks for a change has another domain than `change` or another subject
    than `CHANGE_SUBJECT`, or where `check_subject` refuses it for a ticket
    of any other kind."""
    if kind in ASKS_CHANGE:
        subject = subject.replace("_", "-")
    if not FIELD.fullmatch(subject):
        raise Refused(mctx("`{subject}` is not kebab words").format(subject=subject))
    if kind in ASKS_CHANGE:
        if (domain is not Domain.CHANGE or not CHANGE_SUBJECT.fullmatch(subject)
                or parsed_number(subject) is not None):
            raise Refused(mctx("a `{kind}` takes `change` and `<namespace>-<short-title>`").format(kind=kind))
    else:
        check_subject(tickets, domain, subject)
    return subject
