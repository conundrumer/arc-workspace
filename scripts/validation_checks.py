"""The check a `validation` ticket's `Validation` section gives, and its
refusal by the rules `file_ticket.py sweep --help-all` states, which the
sweep and the move of a `request` into `waiting` both apply."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from ticket_form import section
from ticketing.text import VALIDATION
from transcript_snapshots import Refused

EXERCISED_FIELD = "Exercised:"

COMMAND_FIELD = "Command:"

AGENT_FIELD = "Agent:"

EXERCISED_LINE = re.compile(rf"^- {EXERCISED_FIELD} (?P<pattern>.+)$", re.MULTILINE)

COMMAND_LINE = re.compile(rf"^- {COMMAND_FIELD} `(?P<command>.+)`$", re.MULTILINE)

AGENT_LINE = re.compile(rf"^- {AGENT_FIELD} (?P<agent_type>\S+)$", re.MULTILINE)


@dataclass(frozen=True)
class Check:
    """The check a `validation` ticket's `Validation` section gives."""
    patterns: tuple[re.Pattern[str], ...]
    command: str | None
    agent_types: frozenset[str]


def check_of(path: Path, text: str) -> Check:
    """The check of the ticket at `path` with text `text`, or a refusal
    by the rules `file_ticket.py sweep --help-all` states."""
    body = section(text, VALIDATION)
    commands = [m["command"] for m in COMMAND_LINE.finditer(body)]
    if len(commands) > 1:
        raise Refused(mctx("{path} gives more than one `{field}` line").format(
            path=path, field=COMMAND_FIELD))
    try:
        patterns = tuple(re.compile(m["pattern"]) for m in EXERCISED_LINE.finditer(body))
    except re.error as e:
        raise Refused(mctx("{path} gives an `{field}` pattern that does not compile: "
                           "{error}").format(path=path, field=EXERCISED_FIELD, error=e))
    for pattern in patterns:
        once = json.dumps(pattern.pattern)[1:-1]
        if pattern.search(once) or pattern.search(json.dumps(once)[1:-1]):
            raise Refused(mctx("{path} gives an `{field}` pattern that matches its own "
                               "text in its JSON escape: {pattern}").format(
                path=path, field=EXERCISED_FIELD, pattern=pattern.pattern))
    return Check(patterns, commands[0] if commands else None,
                 frozenset(m["agent_type"] for m in AGENT_LINE.finditer(body)))
