"""The form of a ticket's text, which a filing gives on stdin: its front
matter, its title and its sections."""

import re
from collections.abc import Callable
from pathlib import Path

from controlled_markdown import mctx
from operations.roles import EDITORS
from ticket_files import ticket_path
from ticket_numbers import ticket_number
from ticket_vocabulary import filer_kinds, ticked
from ticketing.text import DESIGN, HEADING_MARK, heading, kind_sections
from ticketing.vocabulary import Kind
from transcript_snapshots import Refused

FRONT = r"---\nkind: (?P<kind>\S+)\n(?P<fields>(?:[a-z-]+: .*\n)*)---\n"


TITLE_MARK = "# "

TICKET_HEAD = re.compile(FRONT + TITLE_MARK)
"""The front matter and title mark of a ticket: at the start of a ticket's
file, for `title`, and in a Bash command, for `call_command` in
`command_labels`, where each match is the head of a ticket the command
files."""


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


def title_line(path: Path, text: str) -> str:
    """The line of `text` that holds its title, with its mark."""
    return TITLE_MARK + title(path, text)


RETIRED = {Kind.REQUEST: "Words"}
"""The section each kind may no longer hold, which `checked_kind`
refuses."""

def sections_example(sections: tuple[str, ...]) -> str:
    """`sections` as the form in the `HELP` of `file_ticket` shows them
    after its title, at the indent of that form."""
    return "".join(f"\n\n    {heading(s)}\n    <its {s.lower()}>" for s in sections)


def body_form(kind: Kind) -> re.Pattern[str]:
    """The title and sections that follow a `kind` ticket's front matter."""
    title = r"# .+\n" if kind is Kind.CHANGE else r"# .+: .+\n"
    sections = kind_sections(kind)
    middle = r"(?:.*\n)*".join(f"{heading(s)}\n" for s in sections[:-1])
    return re.compile(title + r"\n" + middle + r"(?:.*\n)*" + heading(sections[-1]) + r"(?:\n|$)")


VALIDATES = "validates"
"""The field of a `validation` ticket that gives the number of the
`request` it checks."""

FIELDS = {Kind.CHANGE: frozenset({"depends-on", "editors", "after-merge",
                                       "mechanical"}),
          Kind.DELAY: frozenset({"fix"}),
          Kind.VALIDATION: frozenset({VALIDATES})}
"""The front matter fields besides `kind` that each kind may give."""

MECHANICAL = "yes"
"""The one value of a `change`'s `mechanical` field, whose condition the
`HELP` of `file_ticket` gives."""

REQUIRED = {Kind.CHANGE: frozenset({"editors"}), Kind.VALIDATION: frozenset({VALIDATES})}
"""The front matter fields besides `kind` that each kind must give."""


def front_fields(head: re.Match[str]) -> list[tuple[str, str]]:
    """The key and the value of each line of a match of `FRONT`, in order."""
    return [(key, value) for key, value in
            (line.split(": ", 1) for line in head.group("fields").splitlines())]


def list_items(value: str) -> list[str]:
    """The items of a list field, `<item>, <item>`."""
    return [part.strip() for part in value.split(",")]


def editor_names() -> set[str]:
    return {str(r) for r in EDITORS}


def check_fix(value: str) -> None:
    """Refuses a `fix` value that is no editor."""
    if value not in editor_names():
        raise Refused(mctx("`fix` `{value}` is no editor among {known}").format(
            value=value, known=ticked(map(str, EDITORS))))


def check_editors(value: str) -> None:
    """Refuses an `editors` value that is not a list of distinct editors
    (`operations.roles.EDITORS`)."""
    names = list_items(value)
    known = editor_names()
    if not names or any(n not in known for n in names) or len(set(names)) < len(names):
        raise Refused(mctx("`editors` `{value}` is not a list of distinct editors among "
                           "{known}").format(value=value, known=ticked(map(str, EDITORS))))


LOG_SECTION = "Log"

LOG = heading(LOG_SECTION)


HEADING = re.compile(rf"^{re.escape(HEADING_MARK)}.*$", re.MULTILINE)


def section_head(text: str, section: str) -> re.Match[str] | None:
    """The heading line of the section `section` in a ticket's `text`."""
    return re.search(f"^{re.escape(heading(section))}$", text, re.MULTILINE)


def bounds(text: str, name: str) -> tuple[int, int]:
    """Where the lines of the section `name` of a ticket's text start and
    end."""
    head = section_head(text, name)
    if head is None:
        raise Refused(mctx("the ticket has no `{section}` section: its sections are {sections}").format(
            section=heading(name), sections=ticked(m[0] for m in HEADING.finditer(text))))
    nxt = HEADING.search(text, head.end())
    return head.end(), nxt.start() if nxt else len(text)


LINES = re.compile(r":\d+(?:-\d+)?$")


def given_paths(text: str, name: str, root: Path) -> frozenset[str]:
    """The paths the section `name` of the ticket text `text` gives, in
    backticks or as link targets, each with no line or span of lines after
    it: each that is not absolute and holds a `/` or stands at the root of
    the tree `root`. A ticket with no such section gives none."""
    if section_head(text, name) is None:
        return frozenset()
    body = section(text, name)
    words = re.findall(r"`([^`\s]+)`", body) + re.findall(r"\]\(([^)\s]+)\)", body)
    paths = {LINES.sub("", w.split("#", 1)[0].rstrip(":")) for w in words}
    return frozenset(p for p in paths
                     if p and not Path(p).is_absolute() and ("/" in p or (root / p).exists()))


def section(text: str, name: str) -> str:
    start, end = bounds(text, name)
    return text[start:end].strip("\n")


def without_section(text: str, name: str) -> str:
    """A ticket's `text` with the section `name`, its heading with it, cut."""
    _, end = bounds(text, name)
    head = section_head(text, name)
    assert head is not None  # `bounds` refuses a text with no such section.
    return text[:head.start()] + text[end:]


def check_depends_on(tickets: Path, value: str) -> None:
    """Refuses a `depends-on` value that is not a list of numbers of
    tickets the ticket tracker holds."""
    for text in list_items(value):
        ticket_path(tickets, ticket_number(text))


def check_mechanical(value: str) -> None:
    if value != MECHANICAL:
        raise Refused(mctx("`mechanical` `{value}` is not `{yes}`").format(
            value=value, yes=MECHANICAL))


VALUE_CHECKS: dict[str, Callable[[Path, str], None]] = {
    "depends-on": check_depends_on,
    "editors": lambda _tickets, value: check_editors(value),
    "fix": lambda _tickets, value: check_fix(value),
    "mechanical": lambda _tickets, value: check_mechanical(value)}
"""The check of each front matter field that has a value rule; a field
with no entry has none."""


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
    for key, value in front_fields(head):
        if key in keys:
            raise Refused(mctx("the front matter gives `{key}` twice").format(key=key))
        keys.append(key)
        if key not in FIELDS.get(kind, frozenset()):
            raise Refused(mctx("a `{kind}` gives no `{key}`").format(kind=kind, key=key))
        check = VALUE_CHECKS.get(key)
        if check is not None:
            check(tickets, value)
    for key in sorted(REQUIRED.get(kind, frozenset()) - set(keys)):
        raise Refused(mctx("a `{kind}` gives `{key}`").format(kind=kind, key=key))
    if not body_form(kind).match(text, head.end()):
        raise Refused(mctx("the ticket on stdin does not have the form `--help` shows"))
    retired = RETIRED.get(kind)
    if retired is not None and section_head(text, retired):
        raise Refused(mctx("a `{kind}` has no `{section}` section").format(
            kind=kind, section=heading(retired)))
    if section_head(text, LOG_SECTION):
        raise Refused(mctx("the ticket on stdin has a `{log}` section, which the command writes").format(log=LOG))
    return kind


def front(text: str) -> dict[str, str]:
    head = re.match(FRONT, text)
    return {} if head is None else dict(front_fields(head))
