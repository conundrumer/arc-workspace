"""The form of a ticket's text, which a filing gives on stdin: its front
matter, its title and its sections."""

import re
from pathlib import Path

from controlled_markdown import mctx
from ticket_files import ticket_path
from ticket_numbers import parsed_number
from ticket_vocabulary import Kind, filer_kinds, ticked
from transcripts import Refused

FRONT = r"---\nkind: (?P<kind>\S+)\n(?P<fields>(?:[a-z-]+: .*\n)*)---\n"


TICKET_HEAD = re.compile(FRONT + "# ")
"""The front matter and title mark of a ticket, or of an issue filed before
tickets, in the text of a filing command."""


def front_kind(head: re.Match[str]) -> Kind:
    try:
        return Kind(head["kind"])
    except ValueError:
        raise Refused(mctx("`{kind}` is no ticket kind").format(kind=head["kind"]))


def ticket_kind(text: str) -> Kind | None:
    head = re.match(FRONT, text)
    return None if head is None else front_kind(head)


def title(path: Path, text: str) -> str:
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
    for text in (part.strip() for part in value.split(",")):
        number = parsed_number(text)
        if number is None:
            raise Refused(mctx("`{n}` in `depends-on` is not a ticket number").format(n=text))
        ticket_path(tickets, number)


def checked_kind(tickets: Path, agent: str, text: str) -> Kind:
    """The kind of the ticket `text`, refused where `text` does not have
    the form the `HELP` of `file_ticket` shows or `agent` may not file
    that kind."""
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    kind = front_kind(head)
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
