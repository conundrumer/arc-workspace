"""A ticket's file under the main tree's `tickets/`: the form of its name,
with the fields `TicketName` gives it and `name_fields` reads from it, the
directory of each status the file moves between, and the path of a ticket
found by its number or by its name."""

import glob
import re
from collections.abc import Callable, Iterable
from dataclasses import Field, dataclass, field, fields
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from ticket_numbers import TICKET_NUMBER, is_reserved
from ticket_vocabulary import Domain, Status
from transcripts import Refused

FIELD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
"""A field of a ticket's name: kebab words, with no `_`, which separates
the fields."""

SUFFIX = ".md"
"""The end of the name of each ticket's file, numbered or filed before
tickets had numbers."""


PATTERN = "pattern"
"""The key of the metadata of a field of `TicketName` that gives the
pattern its text in a ticket's file name matches."""


@dataclass(frozen=True)
class TicketName:
    """The fields of a ticket's file name, in their order in it. The type of
    each field is a class, which takes the field's text and refuses text
    that is no value of it with a `ValueError`."""
    number: str = field(metadata={PATTERN: TICKET_NUMBER})
    domain: Domain = field(metadata={PATTERN: FIELD})
    subject: str = field(metadata={PATTERN: FIELD})
    agent: str = field(metadata={PATTERN: FIELD})

    @property
    def file_name(self) -> str:
        return joined_name(getattr(self, f.name) for f in fields(self))


def joined_name(parts: Iterable[str], escape: Callable[[str], str] = str) -> str:
    return escape("_").join(parts) + escape(SUFFIX)


NAME_FORM = joined_name(f"<{f.name}>" for f in fields(TicketName))
"""The form of a ticket's file name, as a help text writes it."""

TICKET_NAME = re.compile(joined_name(
    (f"(?P<{f.name}>{f.metadata[PATTERN].pattern})" for f in fields(TicketName)), re.escape))


def field_value(f: Field[Any], text: str) -> Any:
    assert isinstance(f.type, type)
    return f.type(text)


def name_fields(path: Path) -> TicketName | None:
    """The fields of the name of the ticket at `path`, None where the name
    does not have the form `NAME_FORM` gives, as the name of a ticket filed
    before tickets had numbers does not."""
    name = TICKET_NAME.fullmatch(path.name)
    if name is None:
        return None
    try:
        return TicketName(**{f.name: field_value(f, name[f.name]) for f in fields(TicketName)})
    except ValueError:
        return None


def ticket_name(path: Path) -> TicketName:
    name = name_fields(path)
    if name is None:
        raise Refused(mctx("{path} is not named `{form}`").format(path=path, form=NAME_FORM))
    return name


def ticket_number(path: Path) -> str | None:
    name = name_fields(path)
    return name.number if name else None


def statuses(tickets: Path) -> list[Path]:
    return [tickets / s for s in Status]


def ticket_status(path: Path) -> Status:
    """The status the ticket at `path`, a path `ticket_path` gives or one
    under the directory of a status, stands in."""
    return Status(path.parent.name)


def ticket_files(tickets: Path, status: Status) -> list[Path]:
    """The files of the tickets that stand in `status`, in the order of
    their names."""
    return sorted((tickets / status).glob(f"*{SUFFIX}"))


def ticket_path(tickets: Path, ref: str) -> Path:
    """The path of the ticket `ref`, which the help of `file_ticket.py path`
    defines."""
    stem = ref.removesuffix(SUFFIX)
    if not re.fullmatch(r"[\w.-]+", stem):
        raise Refused(mctx("`{ref}` is no ticket number or name").format(ref=ref))
    numbered = bool(TICKET_NUMBER.fullmatch(stem))
    pattern = joined_name((stem, "*"), glob.escape) if numbered else f"{stem}{SUFFIX}"
    found = sorted(p for d in statuses(tickets) for p in d.glob(pattern))
    if len(found) == 1:
        return found[0]
    if found:
        raise Refused(mctx("ticket `{ref}` stands at more than one path: {paths}").format(
            ref=ref, paths=", ".join(str(p) for p in found)))
    if numbered and is_reserved(tickets, stem):
        raise Refused(mctx("ticket number `{ref}` is reserved, and no ticket has it").format(ref=ref))
    raise Refused(mctx("no ticket is `{ref}`").format(ref=ref))
