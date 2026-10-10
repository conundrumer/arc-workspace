"""The text of a ticket that a filing gives on stdin, which the ticket tools
under `scripts/` and the operator's command write: the sections of each
kind and the writer of the text from its title and its sections."""

from collections.abc import Mapping

from ticketing.vocabulary import DEFECT_SECTIONS, Kind

SECTIONS = {Kind.CHANGE: ("Intent", "Motivation", "Scope", "Grounds"),
            Kind.REQUEST: ("Transcript", "Grounds")}
"""The sections of each kind that has its own; every other kind has
`DEFECT_SECTIONS`."""


def kind_sections(kind: Kind) -> tuple[str, ...]:
    """The sections of a `kind` ticket, in order."""
    return SECTIONS.get(kind, DEFECT_SECTIONS)


HEADING_MARK = "## "


def heading(section: str) -> str:
    return f"{HEADING_MARK}{section}"


def ticket_text(kind: Kind, title: str, lines: Mapping[str, str]) -> str:
    """The text of a `kind` ticket with no front matter field besides
    `kind`, whose sections, each with its `lines`, are the kind's own."""
    sections = kind_sections(kind)
    if set(lines) != set(sections):
        raise ValueError(f"the sections {sorted(lines)} are not those of a `{kind}`")
    body = "\n\n".join(f"{heading(s)}\n{lines[s]}" for s in sections)
    return f"---\nkind: {kind.value}\n---\n# {title}\n\n{body}\n"
