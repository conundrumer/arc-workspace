"""The form of a ticket's text, which a filing gives on stdin: its front
matter, its title and its sections, and the fields of its file's name."""

import re
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from ticket_numbers import TICKET_NUMBER, ticket_path
from ticket_vocabulary import Domain, Kind, filer_kinds, ticked
from transcripts import Refused

FIELD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
"""A field of a ticket's name: kebab words, with no `_`, which separates
the fields."""


FRONT = r"---\nkind: (?P<kind>\S+)\n(?P<fields>(?:[a-z-]+: .*\n)*)---\n"


TICKET_HEAD = re.compile(FRONT + "# ")
"""The front matter and title mark of a ticket, or of an issue filed before
tickets, in the text of a filing command."""


TICKET_NAME = re.compile(rf"(?P<number>{TICKET_NUMBER.pattern})_(?P<domain>{FIELD.pattern})"
                         rf"_(?P<subject>{FIELD.pattern})_(?P<agent>{FIELD.pattern})\.md")


@dataclass(frozen=True)
class TicketName:
    """The fields of a ticket's file name."""
    number: str
    domain: Domain
    subject: str
    agent: str

    @property
    def file_name(self) -> str:
        return f"{self.number}_{self.domain}_{self.subject}_{self.agent}.md"


def ticket_name(path: Path) -> TicketName:
    """The fields of the name of the ticket at `path`, refused where the
    name does not have the form `TicketName.file_name` gives, as the name
    of a ticket filed before tickets had numbers does not."""
    name = TICKET_NAME.fullmatch(path.name)
    if name is None or name["domain"] not in set(Domain):
        raise Refused(mctx("{path} is not named `<number>_<domain>_<subject>_<agent>.md`").format(path=path))
    return TicketName(name["number"], Domain(name["domain"]), name["subject"], name["agent"])


def ticket_kind(text: str) -> Kind | None:
    """The kind the front matter of the ticket `text` gives, None where it
    has no front matter that gives one, and refused where it gives a word
    that is no kind."""
    head = re.match(FRONT, text)
    if head is None:
        return None
    try:
        return Kind(head["kind"])
    except ValueError:
        raise Refused(mctx("`{kind}` is no ticket kind").format(kind=head["kind"]))


def title(path: Path, text: str) -> str:
    """The title of the ticket `text`, at `path`, refused where it has no
    front matter and title mark."""
    head = TICKET_HEAD.match(text)
    if head is None:
        raise Refused(mctx("{path} has no front matter and title").format(path=path))
    return text[head.end():].split("\n", 1)[0]


SECTIONS = {Kind.CHANGE: ("Intent", "Motivation", "Scope"),
            Kind.REQUEST: ("Words", "Transcript")}
"""The sections of each kind that has its own; every other kind has
`DEFECT_SECTIONS`."""


DEFECT_SECTIONS = ("Impact", "Evidence")


HEADING_MARK = "## "


def heading(section: str) -> str:
    return f"{HEADING_MARK}{section}"


def sections_example(sections: tuple[str, ...]) -> str:
    """`sections` as the form in the `HELP` of `file_ticket` shows them
    after its title, at the indent of that form."""
    return "".join(f"\n\n    {heading(s)}\n    <its {s.lower()}>" for s in sections)


def body_form(kind: Kind) -> re.Pattern[str]:
    """The title and sections that follow a `kind` ticket's front matter."""
    title = r"# .+\n" if kind is Kind.CHANGE else r"# .+: .+\n"
    sections = SECTIONS.get(kind, DEFECT_SECTIONS)
    middle = r"(?:.*\n)*".join(f"{heading(s)}\n" for s in sections[:-1])
    return re.compile(title + r"\n" + middle + r"(?:.*\n)*" + heading(sections[-1]) + r"(?:\n|$)")


FIELDS = {Kind.CHANGE: frozenset({"depends-on", "priority"})}
"""The front matter fields besides `kind` that each kind may give."""


LOG = heading("Log")


HEADING = re.compile(rf"^{re.escape(HEADING_MARK)}.*$", re.MULTILINE)


def check_depends_on(tickets: Path, value: str) -> None:
    """Refuses a `depends-on` value that is not a list of numbers of
    tickets the ticket tracker holds."""
    for n in (part.strip() for part in value.split(",")):
        if not TICKET_NUMBER.fullmatch(n):
            raise Refused(mctx("`{n}` in `depends-on` is not a ticket number").format(n=n))
        ticket_path(tickets, n)


def checked_kind(tickets: Path, agent: str, text: str) -> Kind:
    """The kind of the ticket `text`, refused where `text` does not have
    the form the `HELP` of `file_ticket` shows or `agent` may not file
    that kind."""
    head = re.match(FRONT, text)
    kind = ticket_kind(text)
    if not head or kind is None:
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    kinds = filer_kinds(agent)
    if kind not in kinds:
        raise Refused(mctx("`{agent}` files no `{kind}`: it files {kinds}").format(
            agent=agent, kind=kind, kinds=ticked(k for k in Kind if k in kinds)))
    keys: list[str] = []
    for line in head.group("fields").splitlines():
        key, value = line.split(": ", 1)
        if key in keys:
            raise Refused(mctx("the front matter gives `{key}` twice").format(key=key))
        keys.append(key)
        if key not in FIELDS.get(kind, frozenset()):
            raise Refused(mctx("a `{kind}` gives no `{key}`").format(kind=kind, key=key))
        if key == "priority" and not (value.isdigit() and 0 <= int(value) <= 100):
            raise Refused(mctx("`priority` `{value}` is not an integer from 0 to 100").format(value=value))
        if key == "depends-on":
            check_depends_on(tickets, value)
    if not body_form(kind).match(text, head.end()):
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    if re.search(f"^{LOG}$", text, re.MULTILINE):
        raise Refused(mctx("the ticket on stdin has a `{log}` section, which the command writes").format(log=LOG))
    return kind
